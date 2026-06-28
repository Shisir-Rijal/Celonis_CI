"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { SendHorizontal } from "lucide-react";
import { clsx } from "clsx";

type ChatComposerProps = {
  onSend: (value: string) => void;
  disabled?: boolean;
};

export default function ChatComposer({ onSend, disabled = false }: ChatComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  const canSend = value.trim().length > 0 && !disabled;

  const submit = () => {
    if (!canSend) return;
    onSend(value);
    setValue("");
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <div className="w-full flex flex-col items-center gap-2 px-6 pb-6 pt-4">
      <div className="w-full max-w-2xl flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message…"
          rows={1}
          style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
          className="flex-1 resize-none rounded-md bg-neutral-grey-30 text-sm text-primary-white placeholder:text-neutral-grey-20 px-4 py-3 outline-none border border-transparent focus:border-neutral-grey-20 transition-colors leading-relaxed overflow-y-auto [&::-webkit-scrollbar]:hidden"
        />
        <button
          type="button"
          onClick={submit}
          disabled={!canSend}
          aria-label="Send message"
          className={clsx(
            "flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full transition-opacity",
            canSend
              ? "bg-secondary-green text-primary-black hover:opacity-90 cursor-pointer"
              : "bg-neutral-grey-30 text-neutral-grey-20 cursor-not-allowed"
          )}
        >
          <SendHorizontal size={16} />
        </button>
      </div>
      <p className="text-[11px] text-neutral-grey-20">
        Press Enter to send · Shift+Enter for new line
      </p>
    </div>
  );
}
