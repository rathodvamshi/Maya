import { useState, useRef, useEffect } from "react";
import { Paperclip, Mic, Send, Sparkles } from "lucide-react";
import { WelcomeScreen } from "./WelcomeScreen";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export const ChatInterface = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsTyping(true);

    // Simulate AI response
    setTimeout(() => {
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "I'm here to help you with that! This is a simulated response. In a real implementation, this would connect to an AI service.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);
      setIsTyping(false);
    }, 2000);
  };

  const handleWelcomeCardClick = (action: string) => {
    const prompts: Record<string, string> = {
      "write-copy": "Help me write engaging copy for my website",
      "image-generation": "Generate a beautiful image for my project",
      "create-avatar": "Create a professional avatar for my profile",
      "write-code": "Help me write clean and efficient code",
    };

    setInputValue(prompts[action] || "");
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex-1 flex flex-col h-screen">
      {/* Header */}
      <header className="border-b border-border bg-card px-8 py-4">
        <h2 className="text-xl font-semibold text-foreground">AI Chat</h2>
      </header>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <WelcomeScreen onCardClick={handleWelcomeCardClick} />
        ) : (
          <div className="max-w-4xl mx-auto p-8 space-y-6">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {isTyping && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-border bg-card p-6">
        <div className="max-w-4xl mx-auto">
          <div className="relative flex items-end gap-3 p-4 rounded-2xl border-2 border-input bg-background focus-within:border-accent-blue transition-all duration-300 focus-within:shadow-lg">
            <Button
              variant="ghost"
              size="sm"
              className="shrink-0 h-10 w-10 p-0 hover:bg-accent-blue/10 hover:text-accent-blue transition-colors"
            >
              <Paperclip className="w-5 h-5" />
            </Button>

            <Textarea
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              className="flex-1 min-h-[40px] max-h-[200px] resize-none border-0 bg-transparent p-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              rows={1}
            />

            <div className="flex items-center gap-2 shrink-0">
              <Button
                variant="ghost"
                size="sm"
                className="h-10 w-10 p-0 hover:bg-accent-blue/10 hover:text-accent-blue transition-colors"
              >
                <Mic className="w-5 h-5" />
              </Button>

              <Button
                variant="ghost"
                size="sm"
                className="h-10 w-10 p-0 hover:bg-accent-purple/10 hover:text-accent-purple transition-colors"
              >
                <Sparkles className="w-5 h-5" />
              </Button>

              <Button
                onClick={handleSendMessage}
                disabled={!inputValue.trim()}
                className="h-10 w-10 p-0 bg-accent-blue hover:bg-accent-blue/90 text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 hover:scale-105"
              >
                <Send className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
