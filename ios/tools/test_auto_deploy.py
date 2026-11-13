"""The iOS launcher's ⋮ menu: Auto deploy, as on Android (android/tools/test_auto_deploy.py). On (the default), the
game opens with Bunker hidden, as before; off, the Bunker menu opens over the game at each launch until DEPLOY is
tapped. Lunar Tear starts before the game either way: it must, before Unity boots."""
import re
import unittest
from pathlib import Path

LAUNCHER = (Path(__file__).resolve().parents[2] / "ios/launcher/LunarLauncher.m").read_text()


class AutoDeploy(unittest.TestCase):
    def test_a_setting_on_by_default(self):
        self.assertRegex(LAUNCHER, r'static BOOL AutoDeploy\(void\) \{\s*NSNumber \*on = \[NSUserDefaults\.standardUserDefaults objectForKey:@"BunkerAutoDeploy"\];\s*return on \? on\.boolValue : YES;\s*\}')

    def test_the_menu_toggles_it(self):
        self.assertIn('AutoDeploy() ? T(@"launcher.menu.auto_deploy_on") : T(@"launcher.menu.auto_deploy_off")', LAUNCHER)
        self.assertRegex(LAUNCHER, r'BOOL on = !AutoDeploy\(\);\s*\[NSUserDefaults\.standardUserDefaults setBool:on forKey:@"BunkerAutoDeploy"\];')
        self.assertIn('on ? Said(@"launcher.menu.auto_deploy_on_toast") : Said(@"launcher.menu.auto_deploy_off_toast")', LAUNCHER)
        # in the Lunar Tear group, beside starting and checking it
        self.assertRegex(LAUNCHER, r'children:@\[server, check, autoDeploy\]')

    def test_off_opens_the_menu_at_launch(self):
        # at launch only (the constructor), not each time the app comes back
        constructor = LAUNCHER[LAUNCHER.index('static void LunarTearLoad(void)'):]
        self.assertRegex(constructor, r'if \(!AutoDeploy\(\)\) gOpenMenu = YES;')
        self.assertLess(constructor.index('if (!AutoDeploy()) gOpenMenu = YES;'), constructor.index('NSString *error = StartServer();'))


if __name__ == "__main__":
    unittest.main()
