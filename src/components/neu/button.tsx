import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface NeuButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "primary" | "danger";
  size?: "sm" | "md" | "lg";
}

const NeuButton = forwardRef<HTMLButtonElement, NeuButtonProps>(
  ({ className, variant = "default", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center font-medium transition-all duration-300 ease-out select-none",
          "active:translate-y-[0.5px] neu-focus",
          size === "sm" && "h-10 px-4 text-sm rounded-2xl",
          size === "md" && "h-12 px-6 text-sm rounded-2xl",
          size === "lg" && "h-14 px-8 text-base rounded-2xl",
          variant === "default" &&
            "bg-[#E0E5EC] text-[#3D4852] shadow-extruded hover:shadow-extruded-hover hover:-translate-y-[1px] active:shadow-inset-sm",
          variant === "primary" &&
            "bg-[#6C63FF] text-white shadow-extruded-accent hover:shadow-extruded-accent-hover hover:-translate-y-[1px] active:shadow-inset-accent",
          variant === "danger" &&
            "bg-[#E0E5EC] text-[#E53E3E] shadow-extruded hover:shadow-extruded-hover hover:-translate-y-[1px] active:shadow-inset-sm",
          className,
        )}
        {...props}
      />
    );
  },
);
NeuButton.displayName = "NeuButton";

export { NeuButton };
export type { NeuButtonProps };
