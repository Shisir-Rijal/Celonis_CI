"use client";

import { clsx } from "clsx";
import type { ChatMessage as ChatMessageType } from "@/lib/chatbot/store";

type ChatMessageProps = {
  message: ChatMessageType;
};

function renderContent(content: string) {
  const lines = content.split("\n");
  return lines.map((line, idx) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g);
    return (
      <span key={idx}>
        {parts.map((part, i) =>
          part.startsWith("**") && part.endsWith("**") ? (
            <strong key={i} className="font-semibold text-primary-white">
              {part.slice(2, -2)}
            </strong>
          ) : (
            <span key={i}>{part}</span>
          )
        )}
        {idx < lines.length - 1 && <br />}
      </span>
    );
  });
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[70%] rounded-md bg-neutral-grey-30 px-4 py-2 text-sm text-primary-white whitespace-pre-wrap leading-relaxed">
          {renderContent(message.content)}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 items-start">
      <span
        aria-hidden
        className="mt-2 h-2 w-2 rounded-full bg-secondary-green flex-shrink-0"
      />
      <div
        className={clsx(
          "max-w-[80%] text-sm text-neutral-grey-10 whitespace-pre-wrap leading-relaxed"
        )}
      >
        {renderContent(message.content)}
      </div>
    </div>
  );
}
