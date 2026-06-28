"use client";

import { useChatbotStore } from "@/lib/chatbot/store";
import ChatSidebar from "./ChatSidebar";
import ChatConversation from "./ChatConversation";
import ChatComposer from "./ChatComposer";

export default function ChatLayout() {
  const sendMessage = useChatbotStore((state) => state.sendMessage);
  const isTyping = useChatbotStore((state) => state.isAssistantTyping);

  return (
    <div className="flex w-full gap-6 h-[calc(100vh-16rem)] min-h-[600px]">
      {/* Sidebar box */}
      <div className="rounded-sm border-2 border-neutral-grey-30 overflow-hidden">
        <ChatSidebar />
      </div>

      {/* Chat panel box */}
      <section className="flex flex-1 flex-col min-w-0 rounded-sm border-2 border-neutral-grey-30 overflow-hidden">
        <ChatConversation />
        <ChatComposer onSend={sendMessage} disabled={isTyping} />
      </section>
    </div>
  );
}
