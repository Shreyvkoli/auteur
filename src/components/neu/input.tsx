import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface NeuInputProps extends InputHTMLAttributes<HTMLInputElement> {
  variant?: "inset" | "inset-deep";
}

const NeuInput = forwardRef<HTMLInputElement, NeuInputProps>(
  ({ className, variant = "inset-deep", ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          "w-full bg-[#E0E5EC] rounded-2xl px-5 py-4 text-sm text-[#3D4852]",
          "placeholder:text-[#A0AEC0]",
          "transition-all duration-300 ease-out",
          "neu-focus",
          variant === "inset" && "shadow-inset",
          variant === "inset-deep" && "shadow-inset-deep",
          className,
        )}
        {...props}
      />
    );
  },
);
NeuInput.displayName = "NeuInput";

interface NeuTextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  variant?: "inset" | "inset-deep";
}

const NeuTextarea = forwardRef<HTMLTextAreaElement, NeuTextareaProps>(
  ({ className, variant = "inset-deep", ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          "w-full bg-[#E0E5EC] rounded-2xl px-5 py-4 text-sm text-[#3D4852] resize-none",
          "placeholder:text-[#A0AEC0]",
          "transition-all duration-300 ease-out",
          "neu-focus",
          variant === "inset" && "shadow-inset",
          variant === "inset-deep" && "shadow-inset-deep",
          className,
        )}
        {...props}
      />
    );
  },
);
NeuTextarea.displayName = "NeuTextarea";

export { NeuInput, NeuTextarea };
export type { NeuInputProps, NeuTextareaProps };
