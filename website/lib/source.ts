import { remarkMdxMermaid } from "fumadocs-core/mdx-plugins";
import { loader } from "fumadocs-core/source";
import { applyMdxPreset } from "fumadocs-mdx/config";
import { defineDocs } from "fumadocs-mdx/macro";

const docs = defineDocs({
  dir: "../docs",
  docs: {
    mdxOptions: applyMdxPreset({
      remarkPlugins: (plugins) => [...plugins, remarkMdxMermaid],
    }),
  },
});

export const source = loader({ baseUrl: "/", source: docs.toFumadocsSource() });
