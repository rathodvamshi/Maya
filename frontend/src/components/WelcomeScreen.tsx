import { Sparkles, ImagePlus, UserCircle, Code } from "lucide-react";

interface WelcomeCardProps {
  icon: React.ElementType;
  title: string;
  color: string;
  delay: number;
  onClick?: () => void;
}

const WelcomeCard = ({ icon: Icon, title, color, delay, onClick }: WelcomeCardProps) => {
  return (
    <button
      onClick={onClick}
      className={`p-6 rounded-2xl border-2 border-transparent hover:border-${color} bg-card hover:shadow-lg transition-all duration-300 hover:scale-105 animate-fade-in-scale group`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className={`w-12 h-12 rounded-xl bg-${color}/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300`}>
        <Icon className={`w-6 h-6 text-${color}`} />
      </div>
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
    </button>
  );
};

interface WelcomeScreenProps {
  onCardClick: (action: string) => void;
}

export const WelcomeScreen = ({ onCardClick }: WelcomeScreenProps) => {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-4xl w-full space-y-12">
        {/* Title */}
        <div className="text-center space-y-4 animate-fade-in">
          <h1 className="text-5xl font-bold text-foreground">
            Welcome to Script
          </h1>
          <p className="text-lg text-muted-foreground">
            Get started by selecting a task and Chat can do the rest...
          </p>
        </div>

        {/* Action Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <WelcomeCard
            icon={Sparkles}
            title="Write Copy"
            color="accent-orange"
            delay={100}
            onClick={() => onCardClick("write-copy")}
          />
          <WelcomeCard
            icon={ImagePlus}
            title="Image Generation"
            color="accent-blue"
            delay={200}
            onClick={() => onCardClick("image-generation")}
          />
          <WelcomeCard
            icon={UserCircle}
            title="Create Avatar"
            color="accent-green"
            delay={300}
            onClick={() => onCardClick("create-avatar")}
          />
          <WelcomeCard
            icon={Code}
            title="Write Code"
            color="accent-purple"
            delay={400}
            onClick={() => onCardClick("write-code")}
          />
        </div>
      </div>
    </div>
  );
};
