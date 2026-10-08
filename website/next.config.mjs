import { fileURLToPath } from "node:url";
import { createMDX } from "fumadocs-mdx/next";

const root = fileURLToPath(new URL("..", import.meta.url));

/** @type {import('next').NextConfig} */
const config = {
  output: "export",
  trailingSlash: true,
  reactStrictMode: true,
  agentRules: false,
  images: { unoptimized: true },
  outputFileTracingRoot: root,
  turbopack: { root },
};

export default createMDX()(config);
