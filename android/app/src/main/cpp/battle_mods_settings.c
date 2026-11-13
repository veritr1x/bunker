// Arena battle mods: the settings file and the per-frame rules (battle_mods_settings.h).
#include "battle_mods_settings.h"

#include <stdio.h>
#include <string.h>

static int is_space(char c) { return c == ' ' || c == '\t' || c == '\r'; }

/** [start, end) without surrounding spaces. */
static void trim(const char **start, const char **end) {
    while (*start < *end && is_space(**start)) (*start)++;
    while (*end > *start && is_space((*end)[-1])) (*end)--;
}

static int equals(const char *start, const char *end, const char *word) {
    size_t n = strlen(word);
    return (size_t)(end - start) == n && memcmp(start, word, n) == 0;
}

void battle_mods_parse(const char *text, BattleMods *out) {
    memset(out, 0, sizeof *out);
    for (const char *line = text; line && *line;) {
        const char *next = strchr(line, '\n');
        const char *end = next ? next : line + strlen(line);
        const char *eq = memchr(line, '=', (size_t)(end - line));
        if (eq) {
            const char *ks = line, *ke = eq, *vs = eq + 1, *ve = end;
            trim(&ks, &ke);
            trim(&vs, &ve);
            int on = equals(vs, ve, "on");
            if (equals(ks, ke, "no_death")) out->no_death = on;
            else if (equals(ks, ke, "one_hit")) out->one_hit = on;
            else if (equals(ks, ke, "zero_cooldown")) out->zero_cooldown = on;
        }
        line = next ? next + 1 : NULL;
    }
}

int battle_mods_format(const BattleMods *mods, char *buf, size_t len) {
    int n = snprintf(buf, len, "no_death=%s\none_hit=%s\nzero_cooldown=%s\n", mods->no_death ? "on" : "off",
                     mods->one_hit ? "on" : "off", mods->zero_cooldown ? "on" : "off");
    return n < 0 || (size_t)n >= len ? -1 : n;
}

int battle_mods_load(const char *path, BattleMods *out) {
    memset(out, 0, sizeof *out);
    FILE *file = path ? fopen(path, "r") : NULL;
    if (!file) return -1;
    char text[512];
    size_t n = fread(text, 1, sizeof text - 1, file);
    int failed = ferror(file);
    fclose(file);
    if (failed) return -1;
    text[n] = 0;
    battle_mods_parse(text, out);
    return 0;
}

int battle_mods_save(const char *path, const BattleMods *mods) {
    char text[128], temp[1100];
    int n = battle_mods_format(mods, text, sizeof text);
    if (!path || n < 0 || snprintf(temp, sizeof temp, "%s.tmp", path) >= (int)sizeof temp) return -1;
    FILE *file = fopen(temp, "w");
    if (!file) return -1;
    int ok = fwrite(text, 1, (size_t)n, file) == (size_t)n;
    ok = (fclose(file) == 0) && ok;
    if (!ok || rename(temp, path) != 0) {
        remove(temp);
        return -1;
    }
    return 0;
}

int battle_mods_is_filler(int max_hp) { return max_hp == BATTLE_MODS_FILLER_HP; }

int battle_mods_player_max(int no_death, int real_max) { return no_death ? BATTLE_MODS_HUGE_HP : real_max; }

int battle_mods_player_hp(int no_death, int hp, int real_max) {
    if (no_death) return BATTLE_MODS_HUGE_HP;
    return hp > real_max ? real_max : hp;
}

int battle_mods_opponent_hp(int one_hit, int hp) { return one_hit && hp > 1 ? 1 : hp; }

int battle_mods_cooltime(int zero_cooldown, int current, int max) { return zero_cooldown && max > 0 ? max : current; }
