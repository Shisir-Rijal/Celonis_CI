"use client";

import { ChevronLeft } from "lucide-react";
import { useChatbotStore } from "@/lib/chatbot/store";
import ChatSidebar from "./ChatSidebar";
import ChatConversation from "./ChatConversation";
import ChatComposer from "./ChatComposer";

export default function ChatLayout() {
  const conversations = useChatbotStore((state) => state.conversations);
  const activeId = useChatbotStore((state) => state.activeConversationId);
  const sendMessage = useChatbotStore((state) => state.sendMessage);
  const isTyping = useChatbotStore((state) => state.isAssistantTyping);

  const active = conversations.find((conv) => conv.id === activeId) ?? null;

  return (
    <div className="flex w-full h-full bg-primary-black border-t border-neutral-grey-30">
      <ChatSidebar />
      <section className="flex flex-1 flex-col min-w-0">
        <header className="flex items-center gap-3 px-6 py-4 border-b border-neutral-grey-30">
          <button
            type="button"
            aria-label="Back"
            className="text-neutral-grey-20 hover:text-primary-white transition-colors cursor-pointer"
          >
            <ChevronLeft size={18} />
          </button>
          <h2 className="text-sm text-neutral-grey-10 font-medium truncate">
            {active?.title ?? "New chat"}
          </h2>
        </header>
        <ChatConversation />
        <ChatComposer onSend={sendMessage} disabled={isTyping} />
      </section>
    </div>
  );
}
