import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface NeuIconWellProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "extruded" | "inset" | "inset-deep";
  size?: "sm" | "md" | "lg";
}

function NeuIconWell({ className, variant = "inset-deep", size = "md", ...props }: NeuIconWellProps) {
  return (
    <div
      className={cn(
        "grid place-items-center bg-[#E0E5EC] transition-all duration-300 ease-out",
        size === "sm" && "h-10 w-10 rounded-xl",
        size === "md" && "h-14 w-14 rounded-2xl",
        size === "lg" && "h-20 w-20 rounded-[32px]",
        variant === "extruded" && "shadow-extruded-sm",
        variant === "inset" && "shadow-inset",
        variant === "inset-deep" && "shadow-inset-deep",
        className,
      )}
      {...props}
    />
  );
}

export { NeuIconWell };
export type { NeuIconWellProps };
