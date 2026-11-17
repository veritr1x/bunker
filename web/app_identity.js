// The builder's App ID and Name for a second copy. webbuild.check_app_identity applies the
// same rules with the same messages before building; app_identity_cases.json holds both to them.
(function (exports) {
  const RULES = {
    android: [/^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$/, 127,  // resources.arsc: 128 UTF-16 units with the ending 0
      "The App ID must be at least two parts separated by dots, each starting with a letter and using only letters, digits and _ (Android)."],
    ios: [/^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$/, 155,
      "The App ID must be at least two parts separated by dots, using only letters, digits and - (iOS)."],
  };
  const GAME_IDS = ["com.square_enix.android_googleplay.nierspww", "com.square_enix.android_googleplay.nierspjp", "com.square-enix.nierspww"];
  const NAME_LIMIT = 30;

  // Python's str.strip() and len() work on code points: trim the same whitespace, count code points.
  const trim = (value) => String(value || "").replace(/^[\s\u001c-\u001f]+|[\s\u001c-\u001f]+$/g, "");

  function checkAppIdentity(platform, appId, appName, portOffset) {
    const id = trim(appId) || null, name = trim(appName) || null, errors = {};
    if (id) {
      const [pattern, limit, message] = RULES[platform];
      if (id.length > limit) errors.appId = "The App ID is too long.";
      else if (!pattern.test(id)) errors.appId = message;
      else if (GAME_IDS.includes(id.toLowerCase())) errors.appId = "That is the game's own ID: leave the field empty for it.";
    }
    if (name && ([...name].length > NAME_LIMIT || /[\u0000-\u001f\u007f]/.test(name)))
      errors.appName = "The name must be 30 characters or fewer, without control characters.";
    // Warnings: the build goes ahead.
    const warnings = {};
    if (id && !errors.appId && Number(portOffset) === 0)
      warnings.portOffset = "With port offset 0 this copy uses the same ports as the other: only one can run at a time. Stop the other copy's server before opening this one, or give this copy its own offset (for example 10000).";
    if (id && !name) warnings.appName = "Without a name, both copies show as NieR.";
    return { errors, warnings, appId: id, appName: name };
  }

  exports.checkAppIdentity = checkAppIdentity;
})(typeof module !== "undefined" ? module.exports : window);
