"use client";

import { useEffect, useRef } from "react";
import { useChatbotStore } from "@/lib/chatbot/store";
import ChatMessage from "./ChatMessage";

export default function ChatConversation() {
  const conversations = useChatbotStore((state) => state.conversations);
  const activeId = useChatbotStore((state) => state.activeConversationId);
  const isTyping = useChatbotStore((state) => state.isAssistantTyping);

  const active = conversations.find((conv) => conv.id === activeId) ?? null;
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [active?.messages.length, isTyping]);

  const hasMessages = active && active.messages.length > 0;

  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto px-6 py-8"
    >
      <div className="mx-auto w-full max-w-2xl">
        {!hasMessages ? (
          <div className="flex h-full min-h-[40vh] items-center justify-center text-center text-sm text-neutral-grey-20">
            Start a conversation by typing a message below.
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {active!.messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            {isTyping && (
              <div className="flex gap-3 items-start">
                <span
                  aria-hidden
                  className="mt-2 h-2 w-2 rounded-full bg-secondary-green animate-pulse"
                />
                <span className="text-sm text-neutral-grey-20">typing…</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
