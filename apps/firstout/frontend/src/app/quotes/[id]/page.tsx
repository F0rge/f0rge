"use client";

import { useParams } from "next/navigation";

import { QuoteEditor } from "../quote-editor";

export default function QuotePage() {
  const { id } = useParams<{ id: string }>();
  return <QuoteEditor key={id} id={id} />;
}
