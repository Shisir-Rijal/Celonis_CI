"use client";

import { create } from "zustand";

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: number;
};

export type Conversation = {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
};

type ChatbotState = {
  conversations: Conversation[];
  activeConversationId: string | null;
  isAssistantTyping: boolean;
  selectConversation: (id: string) => void;
  createConversation: () => string;
  sendMessage: (content: string) => void;
};

const MOCK_REPLY =
  "I'm not connected to a backend yet — this is a placeholder response. Soon I'll be able to give you real competitive insights.";

const initialConversations: Conversation[] = [
  {
    id: "seed-sentiment",
    title: "Sentiment analysis workflow",
    createdAt: Date.now() - 1000 * 60 * 60 * 2,
    messages: [
      {
        id: "seed-sentiment-u1",
        role: "user",
        content: "How do I set up a sentiment analysis pipeline?",
        createdAt: Date.now() - 1000 * 60 * 60 * 2,
      },
      {
        id: "seed-sentiment-a1",
        role: "assistant",
        content:
          "To set up a sentiment analysis pipeline, you typically need three stages:\n\n1. **Data ingestion** — collect text from your sources (social media, reviews, etc.)\n2. **Preprocessing** — clean and tokenize the text\n3. **Model inference** — run a classifier (e.g. BERT, RoBERTa) to score sentiment\n\nWould you like a code example for any of these steps?",
        createdAt: Date.now() - 1000 * 60 * 60 * 2 + 5000,
      },
    ],
  },
  {
    id: "seed-dashboard",
    title: "Dashboard design review",
    createdAt: Date.now() - 1000 * 60 * 60 * 24,
    messages: [],
  },
];

function generateId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function deriveTitle(content: string): string {
  const trimmed = content.trim().replace(/\s+/g, " ");
  if (trimmed.length <= 40) return trimmed;
  return `${trimmed.slice(0, 40)}…`;
}

export const useChatbotStore = create<ChatbotState>((set, get) => ({
  conversations: initialConversations,
  activeConversationId: initialConversations[0]?.id ?? null,
  isAssistantTyping: false,

  selectConversation: (id) => set({ activeConversationId: id }),

  createConversation: () => {
    const id = generateId();
    const next: Conversation = {
      id,
      title: "New chat",
      messages: [],
      createdAt: Date.now(),
    };
    set((state) => ({
      conversations: [next, ...state.conversations],
      activeConversationId: id,
    }));
    return id;
  },

  sendMessage: (content) => {
    const trimmed = content.trim();
    if (!trimmed) return;

    let { activeConversationId } = get();
    if (!activeConversationId) {
      activeConversationId = get().createConversation();
    }

    const userMessage: ChatMessage = {
      id: generateId(),
      role: "user",
      content: trimmed,
      createdAt: Date.now(),
    };

    set((state) => ({
      conversations: state.conversations.map((conv) => {
        if (conv.id !== activeConversationId) return conv;
        const isFirstMessage = conv.messages.length === 0;
        return {
          ...conv,
          title: isFirstMessage ? deriveTitle(trimmed) : conv.title,
          messages: [...conv.messages, userMessage],
        };
      }),
      isAssistantTyping: true,
    }));

    window.setTimeout(() => {
      const assistantMessage: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: MOCK_REPLY,
        createdAt: Date.now(),
      };
      set((state) => ({
        conversations: state.conversations.map((conv) =>
          conv.id === activeConversationId
            ? { ...conv, messages: [...conv.messages, assistantMessage] }
            : conv
        ),
        isAssistantTyping: false,
      }));
    }, 700);
  },
}));
