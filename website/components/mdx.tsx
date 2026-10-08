import defaultComponents, { createRelativeLink } from "fumadocs-ui/mdx";
import type { InferPageType } from "fumadocs-core/source";
import type { ComponentProps } from "react";
import type { MDXComponents } from "mdx/types";
import { source } from "@/lib/source";
import { Mermaid } from "./mermaid";

export function getMDXComponents(page: InferPageType<typeof source>) {
  const RelativeLink = createRelativeLink(source, page);
  return {
    ...defaultComponents,
    Mermaid,
    a: ({ href, ...props }: ComponentProps<"a">) => (
      <RelativeLink
        href={href && /^[^./#][^:]*\.mdx?(#|$)/.test(href) ? `./${href}` : href}
        {...props}
      />
    ),
  } satisfies MDXComponents;
}
