import { useState } from "react";
import { Menu, X, PanelRightClose, PanelRightOpen } from "lucide-react";
import { AppSidebar } from "@/components/AppSidebar";
import { ChatInterface } from "@/components/ChatInterface";
import { ProjectsPanel } from "@/components/ProjectsPanel";
import { Button } from "@/components/ui/button";

const Index = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isProjectsPanelOpen, setIsProjectsPanelOpen] = useState(true);

  return (
    <div className="flex h-screen w-full bg-gradient-app overflow-hidden">
      {/* Mobile Menu Button */}
      <Button
        variant="ghost"
        size="sm"
        className="fixed top-4 left-4 z-50 lg:hidden"
        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
      >
        {isSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </Button>

      {/* Sidebar */}
      <div
        className={`${
          isSidebarOpen ? "translate-x-0" : "-translate-x-full"
        } lg:translate-x-0 transition-transform duration-300 ease-in-out fixed lg:relative z-40 h-full`}
      >
        <AppSidebar />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Projects Panel Toggle Button */}
        <Button
          variant="ghost"
          size="sm"
          className="fixed top-4 right-4 z-50"
          onClick={() => setIsProjectsPanelOpen(!isProjectsPanelOpen)}
        >
          {isProjectsPanelOpen ? (
            <PanelRightClose className="w-5 h-5" />
          ) : (
            <PanelRightOpen className="w-5 h-5" />
          )}
        </Button>

        <div className="flex flex-1 overflow-hidden">
          <ChatInterface />
          <ProjectsPanel isOpen={isProjectsPanelOpen} />
        </div>
      </div>

      {/* Overlay for mobile sidebar */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}
    </div>
  );
};

export default Index;
