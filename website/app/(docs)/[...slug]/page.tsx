import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  DocsBody,
  DocsDescription,
  DocsPage,
  DocsTitle,
} from "fumadocs-ui/layouts/notebook/page";
import { getMDXComponents } from "@/components/mdx";
import { source } from "@/lib/source";
import { site } from "@/lib/site";

type Props = { params: Promise<{ slug: string[] }> };

export default async function Page({ params }: Props) {
  const page = source.getPage((await params).slug);
  if (!page) notFound();
  const MDX = page.data.body;
  return (
    <DocsPage toc={page.data.toc}>
      <DocsTitle>{page.data.title}</DocsTitle>
      <DocsDescription>{page.data.description}</DocsDescription>
      <DocsBody>
        <MDX components={getMDXComponents(page)} />
      </DocsBody>
      <a
        className="source-link"
        href={`${site.repository}/blob/main/docs/${page.path}`}
      >
        View this page on GitHub <span aria-hidden="true">↗</span>
      </a>
    </DocsPage>
  );
}

export function generateStaticParams() {
  return source
    .getPages()
    .filter((page) => page.slugs.length > 0)
    .map((page) => ({ slug: page.slugs }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const page = source.getPage((await params).slug);
  if (!page) notFound();
  return {
    title: page.data.title,
    description: page.data.description,
    alternates: { canonical: page.url },
  };
}
