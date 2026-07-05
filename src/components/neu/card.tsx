import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface NeuCardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "extruded" | "inset" | "inset-deep";
  hover?: "lift" | "none";
  padding?: "sm" | "md" | "lg";
}

const NeuCard = forwardRef<HTMLDivElement, NeuCardProps>(
  ({ className, variant = "extruded", hover = "none", padding = "md", ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "bg-[#E0E5EC] rounded-[32px] transition-all duration-300 ease-out",
          variant === "extruded" && "shadow-extruded",
          variant === "inset" && "shadow-inset",
          variant === "inset-deep" && "shadow-inset-deep",
          hover === "lift" && "hover:shadow-extruded-hover hover:-translate-y-[2px] cursor-pointer",
          padding === "sm" && "p-4",
          padding === "md" && "p-6",
          padding === "lg" && "p-8",
          className,
        )}
        {...props}
      />
    );
  },
);
NeuCard.displayName = "NeuCard";

export { NeuCard };
export type { NeuCardProps };
