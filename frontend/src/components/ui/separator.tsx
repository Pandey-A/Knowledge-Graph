import * as React from "react";

import { cn } from "../../lib/utils";

function Separator({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("h-px w-full bg-slate-800", className)} {...props} />;
}

export { Separator };
