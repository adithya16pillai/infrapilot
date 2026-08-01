import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // This project lives inside the user's home directory, which has its own
  // package-lock.json. Without pinning the root, Turbopack walks up, picks
  // C:\Users\<user> as the workspace root, and dev-mode CSS/font chunks 500.
  // `import.meta.dirname` (not `__dirname`) is what resolves in the ESM config.
  turbopack: {
    root: import.meta.dirname,
  },

  // Next 16 blocks cross-origin dev resources by default. The dev server binds
  // as "localhost", so loading the app via 127.0.0.1 (which Playwright and
  // some browsers do) silently blocks HMR and the page never hydrates.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
