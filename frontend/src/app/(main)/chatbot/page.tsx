"use client";

import ChatLayout from "@components/chatbot/ChatLayout";

export default function ChatbotPage() {
  return (
    <div
      className="w-full -mx-16 -mt-22 -mb-22 flex"
      style={{ width: "calc(100% + 8rem)", height: "calc(100vh - 4rem)" }}
    >
      <ChatLayout />
    </div>
  );
}
