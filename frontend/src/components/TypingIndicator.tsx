import { Bot } from "lucide-react";

export const TypingIndicator = () => {
  return (
    <div className="flex gap-4 animate-fade-in">
      {/* Avatar */}
      <div className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center bg-accent-purple">
        <Bot className="w-5 h-5 text-white" />
      </div>

      {/* Typing Animation */}
      <div className="px-6 py-4 rounded-2xl rounded-tl-none bg-chat-ai border border-border shadow-sm">
        <div className="flex gap-1.5">
          <div className="w-2 h-2 rounded-full bg-muted-foreground/60 animate-typing-dot" />
          <div
            className="w-2 h-2 rounded-full bg-muted-foreground/60 animate-typing-dot"
            style={{ animationDelay: "0.2s" }}
          />
          <div
            className="w-2 h-2 rounded-full bg-muted-foreground/60 animate-typing-dot"
            style={{ animationDelay: "0.4s" }}
          />
        </div>
      </div>
    </div>
  );
};
