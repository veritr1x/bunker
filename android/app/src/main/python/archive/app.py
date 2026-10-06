"""The Archive's pages. Read-only: it never opens the save or stops the game."""
from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import index
from .media import SIZES, VERSION, Models, Motions, Sounds, Textures
from .content import KINDS, Archive, plain, rich

HERE = Path(__file__).resolve().parent
# Pages run only the Archive's own code. The 3D viewer's glTF loader reads embedded textures
# through blob: URLs, with fetch() as well as <img>, so both allow blob:.
POLICY = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
          "img-src 'self' data: blob:; connect-src 'self' blob:; media-src 'self'; frame-ancestors 'none'; "
          "form-action 'self'; base-uri 'none'")
SECTIONS = [("home", "Home", "/"), ("story", "Story", "/story"), ("characters", "Characters", "/characters"),
            ("records", "Records", "/records"), ("movies", "Movies", "/movies"), ("gallery", "Gallery", "/gallery"),
            ("music", "Music", "/music")]


class Builder:
    """Builds the index once, in the background, and reports progress to the setup page."""

    def __init__(self, revision: Path, master: Path, db_path: Path, scenario=None):
        self.revision, self.master, self.db_path, self.scenario = revision, master, db_path, scenario
        self.state = {"running": False, "done": 0, "total": 0, "step": "", "error": ""}
        self.lock = threading.Lock()

    def ready(self) -> bool:
        return not self.state["running"] and self.db_path.exists() and index.is_current(self.db_path, self.revision, self.master)

    def start(self):
        with self.lock:
            if self.state["running"]:
                return
            self.state = {"running": True, "done": 0, "total": 0, "step": "Starting", "error": ""}
        def report(done, total, step):
            self.state.update(done=done, total=total, step=step)
        def run():
            try:
                index.build(self.revision, self.master, self.db_path, report, scenario=self.scenario)
            except Exception as exc:  # shown on the setup page
                self.state["error"] = str(exc) or exc.__class__.__name__
            finally:
                self.state["running"] = False
        threading.Thread(target=run, name="archive-index", daemon=True).start()


def create_app(revision: Path, master: Path, data_dir: Path, static_dir: Path, decode=None, sound=None, model=None,
               motion=None, scenario=None) -> FastAPI:
    """decode(bundle, target_png, max_side), sound(bundle, target_ogg) and model(actor_folder, target_glb) return
    "" or an error; so do motion(clip_bundle, actor_folder, target_json) and scenario(event_map_folder,
    target_json). Without them, no images, sound or 3D, and no speakers or quest chapters."""
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "archive.db"
    builder = Builder(revision, master, db_path, scenario)
    archive = Archive(db_path, revision)
    textures = Textures(revision / "assetbundle", data_dir / "images", decode)
    sounds = Sounds(revision / "assetbundle", data_dir / "sounds", sound)
    models = Models(revision / "assetbundle", data_dir / "models", model)
    motions = Motions(revision / "assetbundle", data_dir / "motions", motion)
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    templates.env.filters["rich"] = rich
    templates.env.filters["plain"] = plain
    # The WebView keeps static files across app updates; their URLs change with their content instead.
    own = sorted(p for p in (HERE / "static").rglob("*") if p.is_file() and "vendor" not in p.parts)
    static_version = hashlib.sha256(b"".join(p.read_bytes() for p in own)).hexdigest()[:12]
    pod_css = Path(static_dir) / "css" / "automata.css"
    pod_version = hashlib.sha256(pod_css.read_bytes()).hexdigest()[:12] if pod_css.is_file() else "0"
    templates.env.globals.update(count=lambda n, word: f"{n} {word}{'' if n == 1 else 's'}", sections=SECTIONS, kinds=KINDS, images=decode is not None, sounds=sound is not None,
                                 asset=lambda path: f"/archive-static/{path}?v={static_version}",
                                 pod_css=f"/static/css/automata.css?v={pod_version}",
                                 img=lambda size, path: f"/media/image/{size}/{path}?v={VERSION}",
                                 snd=lambda path: f"/media/audio/{path}?v={VERSION}",
                                 mdl=lambda asset: f"/media/model/{asset}.glb?v={VERSION}",
                                 mtn=lambda asset, clip: f"/media/motion/{asset}/{clip}.json?v={VERSION}",
                                 has_model=lambda asset: model is not None and models.has(asset))

    app = FastAPI(title="Archive", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.mount("/archive-static", StaticFiles(directory=str(HERE / "static")), name="archive-static")

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def page(request: Request, name: str, active: str, **values):
        values.update(request=request, active=active, theme=request.cookies.get("lunar_theme", ""))
        return templates.TemplateResponse(request, name, values)

    def need_index(request: Request):
        if not builder.ready():
            raise HTTPException(status_code=307, headers={"Location": "/setup"})

    @app.get("/")
    def home(request: Request):
        if not builder.ready():
            return RedirectResponse("/setup")
        summary = archive.meta("summary")
        return page(request, "home.html", "home", built=archive.meta("built", ""), summary=summary,
                    counts={"movies": sum(len(g["items"]) for g in archive.movies())})

    @app.get("/setup")
    def setup(request: Request):
        if builder.ready():
            return RedirectResponse("/")
        if not builder.state["running"] and not builder.state["error"]:
            builder.start()
        return page(request, "setup.html", "home", state=builder.state)

    @app.post("/setup/retry")
    def retry():
        builder.state["error"] = ""
        builder.start()
        return RedirectResponse("/setup", status_code=303)

    @app.get("/api/status")
    def status():
        return JSONResponse({**builder.state, "ready": builder.ready()})

    @app.get("/story")
    def story(request: Request, tab: str = "main"):
        need_index(request)
        values = {"tab": tab}
        if tab == "main":
            values["seasons"] = archive.main_chapters()
        elif tab == "recollections":
            values["groups"] = archive.recollections()
        else:
            kinds = ["eid", "lid", "cid", "vid"] if tab == "sub" else ["sid"]
            values["groups"] = [{"kind": k, "name": KINDS[k], "items": archive.sub_groups(k)} for k in kinds]
        return page(request, "story.html", "story", **values)

    @app.get("/story/main/{season}/{chapter}")
    def chapter(request: Request, season: int, chapter: int):
        need_index(request)
        number, title = archive.chapter_label(season, chapter)
        return page(request, "scenes.html", "story", heading=number, title=title, crumb=archive.season_title(season),
                    scenes=archive.scenes(area="main", season=season, chapter=chapter))

    @app.get("/story/{kind}/{grp}")
    def group(request: Request, kind: str, grp: str):
        need_index(request)
        if kind not in KINDS:
            raise HTTPException(404)
        return page(request, "scenes.html", "story", heading=f"{KINDS[kind]} · {grp.upper()}", title="",
                    crumb=KINDS[kind], scenes=archive.scenes(kind=kind, grp=grp))

    @app.get("/scene/{scene_id}")
    def scene(request: Request, scene_id: int):
        need_index(request)
        found = archive.scene(scene_id)
        if not found:
            raise HTTPException(404)
        if found["area"] == "main":
            number, title = archive.chapter_label(found["season"], found["chapter"])
            back, place = f"/story/main/{found['season']}/{found['chapter']}", number
        else:
            back, place = f"/story/{found['kind']}/{found['grp']}", KINDS.get(found["kind"], found["kind"])
        return page(request, "reader.html", "story", scene=found, back=back, place=place)

    @app.get("/records")
    def records(request: Request, tab: str = "weapons"):
        need_index(request)
        values = {"tab": tab}
        if tab == "weapons":
            values["weapons"] = archive.weapons()
        elif tab == "reports":
            values["groups"] = archive.reports()
        elif tab == "archives":
            values["items"] = archive.lost_archives()
        else:
            values["items"] = archive.debris()
        return page(request, "records.html", "records", **values)

    @app.get("/movies")
    def movies(request: Request, play: str = ""):
        need_index(request)
        groups = archive.movies()
        current = next((m for g in groups for m in g["items"] if m["file"] == play), None)
        return page(request, "movies.html", "movies", groups=groups, current=current)

    @app.get("/media/movie/{name}")
    def movie_file(name: str):
        target = (revision / "resources" / name).resolve()
        if target.parent != (revision / "resources").resolve() or target.suffix != ".mp4" or not target.is_file():
            raise HTTPException(404)
        return FileResponse(target, media_type="video/mp4")

    @app.get("/characters")
    def characters(request: Request):
        need_index(request)
        return page(request, "characters.html", "characters", characters=archive.characters())

    @app.get("/characters/{character_id}")
    def character(request: Request, character_id: int):
        need_index(request)
        found = archive.character(character_id)
        if not found:
            raise HTTPException(404)
        return page(request, "character.html", "characters", character=found)

    @app.get("/costume/{asset}")
    def costume(request: Request, asset: str):
        need_index(request)
        found = archive.costume(asset)
        if not found:
            raise HTTPException(404)
        return page(request, "costume.html", "characters", costume=found)

    @app.get("/viewer/{asset}")
    def viewer(request: Request, asset: str):
        need_index(request)
        found = archive.costume(asset)
        if not found or model is None or not models.has(asset):
            raise HTTPException(404)
        return page(request, "viewer.html", "characters", costume=found,
                    motions=archive.motions(asset) if motion is not None else [])

    @app.get("/media/model/{asset}.glb")
    def model_file(asset: str):
        try:
            glb = models.glb(asset)
        except FileNotFoundError:
            raise HTTPException(404)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return FileResponse(glb, media_type="model/gltf-binary", headers={"Cache-Control": "private, max-age=86400"})

    @app.get("/media/motion/{asset}/{clip}.json")
    def motion_file(asset: str, clip: str):
        try:
            data = motions.json(asset, clip)
        except FileNotFoundError:
            raise HTTPException(404)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return FileResponse(data, media_type="application/json", headers={"Cache-Control": "private, max-age=86400"})

    @app.get("/gallery")
    def gallery(request: Request, tab: str = "stills"):
        need_index(request)
        tabs = dict(Archive.GALLERY_TABS)
        if tab not in tabs:
            raise HTTPException(404)
        return page(request, "gallery.html", "gallery", tab=tab, tabs=Archive.GALLERY_TABS, groups=archive.gallery(tab))

    @app.get("/gallery/{category}/{grp}")
    def gallery_group(request: Request, category: str, grp: str):
        need_index(request)
        found = archive.gallery_images(category, grp)
        if not found:
            raise HTTPException(404)
        return page(request, "gallery_group.html", "gallery", category=category, tabs=dict(Archive.GALLERY_TABS),
                    label=archive.group_label(category, grp), items=found)

    @app.get("/image")
    def image(request: Request, path: str):
        need_index(request)
        found = archive.image(path)
        if not found:
            raise HTTPException(404)
        return page(request, "image.html", "gallery", image=found, tabs=dict(Archive.GALLERY_TABS))

    @app.get("/media/image/{size}/{path:path}")
    def image_file(size: str, path: str):
        if size not in SIZES:
            raise HTTPException(404)
        try:
            png = textures.png(path, size)
        except FileNotFoundError:
            raise HTTPException(404)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return FileResponse(png, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})

    @app.get("/music")
    def music(request: Request):
        need_index(request)
        return page(request, "music.html", "music", tracks=archive.music())

    @app.get("/media/audio/{path:path}")
    def audio_file(path: str):
        try:
            ogg = sounds.ogg(path)
        except FileNotFoundError:
            raise HTTPException(404)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return FileResponse(ogg, media_type="audio/ogg", headers={"Cache-Control": "private, max-age=86400"})

    @app.get("/search")
    def search(request: Request, q: str = ""):
        need_index(request)
        return page(request, "search.html", "home", q=q, results=archive.search(q))

    return app
