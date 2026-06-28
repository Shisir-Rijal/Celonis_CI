"use client";

import { clsx } from "clsx";
import { Plus, MessageSquare } from "lucide-react";
import { useChatbotStore } from "@/lib/chatbot/store";

export default function ChatSidebar() {
  const conversations = useChatbotStore((state) => state.conversations);
  const activeId = useChatbotStore((state) => state.activeConversationId);
  const selectConversation = useChatbotStore((state) => state.selectConversation);
  const createConversation = useChatbotStore((state) => state.createConversation);

  return (
    <aside className="flex flex-col h-full w-64 flex-shrink-0 bg-primary-black">
      <div className="flex items-center justify-between px-4 py-4 border-b border-neutral-grey-30">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="h-2 w-2 rounded-full bg-secondary-green"
          />
          <span className="text-sm font-medium text-primary-white">Assistant</span>
        </div>
        <button
          type="button"
          onClick={() => createConversation()}
          className="flex items-center gap-1 text-xs text-secondary-green border border-neutral-grey-30 hover:border-secondary-green rounded-sm px-2 py-1 transition-colors cursor-pointer"
        >
          <Plus size={12} />
          New
        </button>
      </div>

      <div className="px-4 pt-4 pb-2">
        <span className="text-[11px] tracking-[0.18em] uppercase text-neutral-grey-20">
          Recent
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-4 flex flex-col gap-1">
        {conversations.map((conv) => {
          const isActive = conv.id === activeId;
          return (
            <button
              key={conv.id}
              type="button"
              onClick={() => selectConversation(conv.id)}
              className={clsx(
                "flex items-center gap-2 w-full text-left text-sm rounded-sm px-3 py-2 transition-colors cursor-pointer truncate",
                isActive
                  ? "bg-neutral-grey-30 text-primary-white"
                  : "text-neutral-grey-20 hover:text-primary-white hover:bg-neutral-grey-30/50"
              )}
            >
              <MessageSquare size={14} className="flex-shrink-0" />
              <span className="truncate">{conv.title}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
