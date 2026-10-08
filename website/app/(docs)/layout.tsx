import type { ReactNode } from "react";
import { DocsLayout } from "fumadocs-ui/layouts/notebook";
import { source } from "@/lib/source";
import { layoutOptions } from "@/lib/site";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <DocsLayout
      {...layoutOptions}
      tree={source.getPageTree()}
      nav={{ ...layoutOptions.nav, mode: "top" }}
      tabs={false}
    >
      {children}
    </DocsLayout>
  );
}
