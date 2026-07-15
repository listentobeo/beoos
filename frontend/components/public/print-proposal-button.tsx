"use client";

import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";

export function PrintProposalButton() {
  return (
    <Button type="button" variant="outline" onClick={() => window.print()} className="print:hidden">
      <Printer className="size-4" />
      Print / save PDF
    </Button>
  );
}
