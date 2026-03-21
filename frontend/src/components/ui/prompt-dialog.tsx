/**
 * Prompt Dialog Component
 * =======================
 *
 * A styled input dialog that replaces window.prompt().
 */
import { memo, useCallback, useEffect, useRef, useState } from "react";
import { PencilLine } from "lucide-react";
import { Button } from "./button";
import { Input } from "./input";
import { cn } from "@/lib/utils";

interface PromptDialogProps {
  open: boolean;
  onSubmit: (value: string) => void;
  onCancel: () => void;
  title?: string;
  message?: string;
  placeholder?: string;
  defaultValue?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  iconVariant?: "default" | "primary";
}

export const PromptDialog = memo(function PromptDialog({
  open,
  onSubmit,
  onCancel,
  title = "Enter a value",
  message,
  placeholder,
  defaultValue = "",
  confirmLabel = "Continue",
  cancelLabel = "Cancel",
  iconVariant = "primary",
}: PromptDialogProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState(defaultValue);

  useEffect(() => {
    if (!open) return;
    setValue(defaultValue);
    const t = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(t);
  }, [open, defaultValue]);

  const submit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
  }, [onSubmit, value]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
      if (e.key === "Enter") submit();
    },
    [onCancel, submit]
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      onKeyDown={handleKeyDown}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onCancel}
      />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="prompt-title"
        className="relative z-10 w-full max-w-md mx-4 rounded-xl bg-card border border-border shadow-2xl animate-in zoom-in-95 fade-in duration-200"
      >
        <div className="p-6">
          <div className="flex items-start gap-4">
            <div
              className={cn(
                "flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center",
                iconVariant === "primary" ? "bg-primary/15" : "bg-muted"
              )}
            >
              <PencilLine
                className={cn(
                  "w-5 h-5",
                  iconVariant === "primary" ? "text-primary" : "text-foreground"
                )}
              />
            </div>
            <div className="flex-1 min-w-0">
              <h3 id="prompt-title" className="text-lg font-semibold leading-tight">
                {title}
              </h3>
              {message ? (
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                  {message}
                </p>
              ) : null}
              <div className="mt-4">
                <Input
                  ref={inputRef}
                  value={value}
                  placeholder={placeholder}
                  onChange={(e) => setValue(e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border/50 bg-muted/20 rounded-b-xl">
          <Button variant="ghost" size="sm" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button size="sm" onClick={submit} disabled={!value.trim()}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
});

