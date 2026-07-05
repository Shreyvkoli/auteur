import { type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface NeuSectionProps {
  title: string;
  icon?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

function NeuSection({ title, icon, action, children, className }: NeuSectionProps) {
  return (
    <section className={cn("mt-10", className)}>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2.5 font-display text-sm font-bold tracking-tight text-[#3D4852]">
          {icon && <span className="text-[#6C63FF]">{icon}</span>}
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export { NeuSection };
export type { NeuSectionProps };
