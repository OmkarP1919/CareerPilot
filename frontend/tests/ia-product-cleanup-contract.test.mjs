import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

console.log("Starting IA / Product Cleanup (Phase 7.0C.4) Contract Tests...\n");

// -----------------------------------------------------------------------------
// A. Insights Navigation
// -----------------------------------------------------------------------------
const sidebarPath = path.join(ROOT, "src", "components", "Sidebar.jsx");
assert.ok(fs.existsSync(sidebarPath), "Sidebar.jsx must exist");
const sidebarSrc = fs.readFileSync(sidebarPath, "utf8");

// Insights must be in primaryNavItems (Workspace section)
const primaryNavMatch = sidebarSrc.match(/const\s+primaryNavItems\s*=\s*\[([\s\S]*?)\];/);
assert.ok(primaryNavMatch, "Sidebar.jsx must declare primaryNavItems");
assert.ok(
  primaryNavMatch[1].includes('to: "/insights"') || primaryNavMatch[1].includes("to: '/insights'"),
  "Insights must be categorized under primaryNavItems (Workspace)"
);

// Insights must NOT be in secondaryNavItems (Account section)
const secondaryNavMatch = sidebarSrc.match(/const\s+secondaryNavItems\s*=\s*\[([\s\S]*?)\];/);
assert.ok(secondaryNavMatch, "Sidebar.jsx must declare secondaryNavItems");
assert.ok(
  !secondaryNavMatch[1].includes('to: "/insights"') && !secondaryNavMatch[1].includes("to: '/insights'"),
  "Insights must not be categorized under secondaryNavItems (Account)"
);

// Mobile Account access remains intact via AccountMenu.jsx
const accountMenuPath = path.join(ROOT, "src", "components", "AccountMenu.jsx");
assert.ok(fs.existsSync(accountMenuPath), "AccountMenu.jsx must exist");
const accountMenuSrc = fs.readFileSync(accountMenuPath, "utf8");
assert.ok(
  accountMenuSrc.includes('to: "/insights"') || accountMenuSrc.includes("to: '/insights'"),
  "AccountMenu.jsx must retain /insights for mobile Account access"
);

// Route aliases in App.jsx remain preserved
const appJsxPath = path.join(ROOT, "src", "App.jsx");
const appJsx = fs.readFileSync(appJsxPath, "utf8");
assert.ok(
  appJsx.includes('path="/analytics"') && appJsx.includes('to="/insights"'),
  "App.jsx must retain canonical redirect /analytics -> /insights"
);
assert.ok(
  appJsx.includes('path="/insights"') && appJsx.includes("<AnalyticsPage"),
  "App.jsx must retain /insights route rendering AnalyticsPage"
);
console.log("  ok   A. Insights navigation in Workspace and mobile access verified");

// -----------------------------------------------------------------------------
// B. Settings Ownership
// -----------------------------------------------------------------------------
const settingsPath = path.join(ROOT, "src", "pages", "SettingsPage.jsx");
assert.ok(fs.existsSync(settingsPath), "SettingsPage.jsx must exist");
const settingsSrc = fs.readFileSync(settingsPath, "utf8");

// No editable preferred_roles or preferred_locations controls
assert.ok(
  !settingsSrc.includes("preferred_roles"),
  "SettingsPage must not contain preferred_roles state or inputs"
);
assert.ok(
  !settingsSrc.includes("preferred_locations"),
  "SettingsPage must not contain preferred_locations state or inputs"
);
assert.ok(
  !settingsSrc.includes('api.put("/profile"'),
  "SettingsPage must not make PUT /profile mutation calls"
);

// Settings contains reference card and profile link
assert.ok(
  settingsSrc.includes("Career & Job Search Preferences") ||
  settingsSrc.includes("Career &amp; Job Search Preferences"),
  "SettingsPage must render 'Career & Job Search Preferences' heading"
);
assert.ok(
  settingsSrc.includes("Edit in Profile"),
  "SettingsPage must render 'Edit in Profile' action button"
);
assert.ok(
  settingsSrc.includes('to="/profile"'),
  "SettingsPage action must navigate to /profile"
);
console.log("  ok   B. Settings ownership and single source-of-truth reference card verified");

// -----------------------------------------------------------------------------
// C. Auth Messaging
// -----------------------------------------------------------------------------
const loginPath = path.join(ROOT, "src", "pages", "LoginPage.jsx");
const signupPath = path.join(ROOT, "src", "pages", "SignUpPage.jsx");
assert.ok(fs.existsSync(loginPath), "LoginPage.jsx must exist");
assert.ok(fs.existsSync(signupPath), "SignUpPage.jsx must exist");
const loginSrc = fs.readFileSync(loginPath, "utf8");
const signupSrc = fs.readFileSync(signupPath, "utf8");

const forbiddenStrings = [
  "Unable to reach the backend server",
  "backend API is running",
  "Backend database or server error",
  "Backend error:",
  "Backend synchronization failed",
  "Add localhost to Authorized Domains",
  "Firebase Console",
];

for (const s of forbiddenStrings) {
  assert.ok(!loginSrc.includes(s), `LoginPage must not expose developer string: '${s}'`);
  assert.ok(!signupSrc.includes(s), `SignUpPage must not expose developer string: '${s}'`);
}

// Ensure user-friendly error messages are used
const expectedUserMessages = [
  "Unable to connect to the server. Please check your internet connection and try again.",
  "Our service is temporarily unavailable. Please try again in a few moments.",
  "Network error. Please check your internet connection and try again.",
];
for (const msg of expectedUserMessages) {
  assert.ok(loginSrc.includes(msg), `LoginPage must include user-friendly message: '${msg}'`);
  assert.ok(signupSrc.includes(msg), `SignUpPage must include user-friendly message: '${msg}'`);
}
console.log("  ok   C. Auth messaging user-friendliness and developer-string absence verified");

// -----------------------------------------------------------------------------
// D. Dead Component Cleanup
// -----------------------------------------------------------------------------
const deletedFiles = [
  "src/components/Header.jsx",
  "src/components/MobileNav.jsx",
  "src/components/MobileMoreMenu.jsx",
  "src/components/ComingSoon.jsx",
  "src/components/OnboardingModal.jsx",
  "src/components/StatusBadge.jsx",
  "src/components/ui/Button.jsx",
  "src/components/ui/Card.jsx",
  "src/components/ui/Input.jsx",
];

for (const rel of deletedFiles) {
  const fullPath = path.join(ROOT, rel);
  assert.ok(!fs.existsSync(fullPath), `Dead component file must be deleted: ${rel}`);
}

// Verify no active source file imports any of the deleted components
const srcDir = path.join(ROOT, "src");
function getAllSourceFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...getAllSourceFiles(full));
    } else if (/\.(jsx?|mjs)$/.test(entry.name)) {
      files.push(full);
    }
  }
  return files;
}

const allSrcFiles = getAllSourceFiles(srcDir);
const deadComponentNames = [
  "MobileNav",
  "MobileMoreMenu",
  "ComingSoon",
  "OnboardingModal",
  "StatusBadge",
];

for (const filePath of allSrcFiles) {
  const content = fs.readFileSync(filePath, "utf8");
  for (const compName of deadComponentNames) {
    assert.ok(
      !content.includes(`/${compName}`) && !content.includes(`"${compName}"`),
      `Source file ${filePath} must not reference dead component ${compName}`
    );
  }
  // Check ui/Button, ui/Card, ui/Input
  assert.ok(
    !content.includes("/ui/Button") && !content.includes("/ui/Card") && !content.includes("/ui/Input"),
    `Source file ${filePath} must not reference deleted ui components`
  );
  // Check Header.jsx (avoiding generic word header)
  assert.ok(
    !content.includes('from "./Header"') && !content.includes('from "../Header"'),
    `Source file ${filePath} must not import deleted Header component`
  );
}
console.log("  ok   D. Dead components removal and reference absence verified");

// -----------------------------------------------------------------------------
// E. TopNav Cleanup
// -----------------------------------------------------------------------------
const topNavPath = path.join(ROOT, "src", "components", "TopNav.jsx");
assert.ok(fs.existsSync(topNavPath), "TopNav.jsx must exist");
const topNavSrc = fs.readFileSync(topNavPath, "utf8");

// Assert dead state and unreachable DOM removed
assert.ok(!topNavSrc.includes("menuOpen"), "TopNav must not contain dead menuOpen state");
assert.ok(!topNavSrc.includes("setMenuOpen"), "TopNav must not contain dead setMenuOpen state");
assert.ok(!topNavSrc.includes("menuRef"), "TopNav must not contain dead menuRef");
assert.ok(!topNavSrc.includes("<AccountMenu"), "TopNav must not render unreachable desktop AccountMenu");
assert.ok(!topNavSrc.includes('import AccountMenu from "./AccountMenu";'), "TopNav must not import AccountMenu");

// Assert avatar, username, and mobile onAvatarClick are intact
assert.ok(topNavSrc.includes("onAvatarClick"), "TopNav must accept onAvatarClick prop");
assert.ok(topNavSrc.includes("onAvatarClick?.()"), "TopNav button must invoke onAvatarClick");
assert.ok(topNavSrc.includes("topnav-avatar"), "TopNav must preserve topnav-avatar element");
assert.ok(topNavSrc.includes("topnav-username"), "TopNav must preserve topnav-username element");

// MainLayout wires TopNav onAvatarClick to toggleSheet
const mainLayoutPath = path.join(ROOT, "src", "layouts", "MainLayout.jsx");
assert.ok(fs.existsSync(mainLayoutPath), "MainLayout.jsx must exist");
const mainLayoutSrc = fs.readFileSync(mainLayoutPath, "utf8");
assert.ok(
  mainLayoutSrc.includes("<TopNav onAvatarClick={toggleSheet}"),
  "MainLayout must pass toggleSheet to TopNav onAvatarClick"
);
console.log("  ok   E. TopNav dead state cleanup and mobile avatar behavior verified");

console.log("\nAll IA / Product Cleanup (Phase 7.0C.4) contract tests passed successfully!");
