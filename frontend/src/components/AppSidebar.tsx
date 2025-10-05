import { useState } from "react";
import { 
  MessageSquarePlus, 
  FolderKanban, 
  CheckSquare, 
  Clock, 
  History, 
  FileText, 
  FileCode, 
  Users, 
  Settings, 
  HelpCircle,
  ChevronDown,
  ChevronRight,
  User,
  MoreVertical,
  Pin,
  Trash2,
  Edit2,
  Check
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface SidebarItemProps {
  icon: React.ElementType;
  label: string;
  hasDropdown?: boolean;
  active?: boolean;
  onClick?: () => void;
}

const SidebarItem = ({ icon: Icon, label, hasDropdown, active, onClick }: SidebarItemProps) => {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-300 group ${
        active 
          ? "bg-sidebar-accent text-sidebar-accent-foreground" 
          : "hover:bg-sidebar-accent/50 text-sidebar-foreground"
      }`}
    >
      <Icon className={`w-5 h-5 transition-all duration-300 ${
        active ? "text-accent-blue" : "group-hover:text-accent-blue group-hover:scale-110"
      }`} />
      <span className="flex-1 text-left text-sm font-medium">{label}</span>
      {hasDropdown && <ChevronDown className="w-4 h-4" />}
    </button>
  );
};

interface TaskItem {
  id: string;
  title: string;
  pinned?: boolean;
}

const TasksDropdown = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [pendingTasks] = useState<TaskItem[]>([
    { id: "1", title: "Design new landing page", pinned: true },
    { id: "2", title: "Review pull requests" },
    { id: "3", title: "Update documentation" },
  ]);
  const [completedTasks] = useState<TaskItem[]>([
    { id: "4", title: "Setup CI/CD pipeline" },
    { id: "5", title: "Implement dark mode" },
  ]);

  return (
    <div className="space-y-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-300 hover:bg-sidebar-accent/50 text-sidebar-foreground"
      >
        <CheckSquare className="w-5 h-5 transition-all duration-300 group-hover:text-accent-blue" />
        <span className="flex-1 text-left text-sm font-medium">Tasks</span>
        {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
      </button>
      
      {isOpen && (
        <div className="ml-4 mr-2 animate-accordion-down">
          <Tabs defaultValue="pending" className="w-full">
            <TabsList className="w-full bg-sidebar-accent/30">
              <TabsTrigger value="pending" className="flex-1 text-xs">Pending</TabsTrigger>
              <TabsTrigger value="completed" className="flex-1 text-xs">Completed</TabsTrigger>
            </TabsList>
            <TabsContent value="pending" className="space-y-1 mt-2">
              {pendingTasks.map((task) => (
                <div key={task.id} className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-sidebar-accent/30 group">
                  {task.pinned && <Pin className="w-3 h-3 text-accent-blue" />}
                  <span className="flex-1 text-xs text-sidebar-foreground/80">{task.title}</span>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100">
                        <MoreVertical className="w-3 h-3" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="bg-popover">
                      <DropdownMenuItem><Check className="w-3 h-3 mr-2" />Complete</DropdownMenuItem>
                      <DropdownMenuItem><Pin className="w-3 h-3 mr-2" />Pin</DropdownMenuItem>
                      <DropdownMenuItem><Edit2 className="w-3 h-3 mr-2" />Rename</DropdownMenuItem>
                      <DropdownMenuItem className="text-destructive"><Trash2 className="w-3 h-3 mr-2" />Delete</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              ))}
            </TabsContent>
            <TabsContent value="completed" className="space-y-1 mt-2">
              {completedTasks.map((task) => (
                <div key={task.id} className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-sidebar-accent/30 group">
                  <span className="flex-1 text-xs text-sidebar-foreground/60 line-through">{task.title}</span>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100">
                        <MoreVertical className="w-3 h-3" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="bg-popover">
                      <DropdownMenuItem><Edit2 className="w-3 h-3 mr-2" />Rename</DropdownMenuItem>
                      <DropdownMenuItem className="text-destructive"><Trash2 className="w-3 h-3 mr-2" />Delete</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              ))}
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
};

const HistoryDropdown = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [recentChats] = useState([
    { id: "1", title: "Design system discussion" },
    { id: "2", title: "API integration help" },
    { id: "3", title: "Bug fixing session" },
  ]);
  const [savedChats] = useState([
    { id: "4", title: "Important project notes" },
  ]);

  return (
    <div className="space-y-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-300 hover:bg-sidebar-accent/50 text-sidebar-foreground"
      >
        <History className="w-5 h-5 transition-all duration-300 group-hover:text-accent-blue" />
        <span className="flex-1 text-left text-sm font-medium">History</span>
        {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
      </button>
      
      {isOpen && (
        <div className="ml-4 mr-2 animate-accordion-down">
          <Tabs defaultValue="recent" className="w-full">
            <TabsList className="w-full bg-sidebar-accent/30">
              <TabsTrigger value="recent" className="flex-1 text-xs">Recent</TabsTrigger>
              <TabsTrigger value="saved" className="flex-1 text-xs">Saved</TabsTrigger>
            </TabsList>
            <TabsContent value="recent" className="space-y-1 mt-2">
              {recentChats.map((chat) => (
                <div key={chat.id} className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-sidebar-accent/30 group">
                  <Clock className="w-3 h-3 text-muted-foreground" />
                  <span className="flex-1 text-xs text-sidebar-foreground/80 truncate">{chat.title}</span>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100">
                        <MoreVertical className="w-3 h-3" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="bg-popover">
                      <DropdownMenuItem><Pin className="w-3 h-3 mr-2" />Save</DropdownMenuItem>
                      <DropdownMenuItem className="text-destructive"><Trash2 className="w-3 h-3 mr-2" />Delete</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              ))}
            </TabsContent>
            <TabsContent value="saved" className="space-y-1 mt-2">
              {savedChats.map((chat) => (
                <div key={chat.id} className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-sidebar-accent/30 group">
                  <Pin className="w-3 h-3 text-accent-blue" />
                  <span className="flex-1 text-xs text-sidebar-foreground/80 truncate">{chat.title}</span>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100">
                        <MoreVertical className="w-3 h-3" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="bg-popover">
                      <DropdownMenuItem className="text-destructive"><Trash2 className="w-3 h-3 mr-2" />Delete</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              ))}
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
};

export const AppSidebar = () => {
  const [activeItem, setActiveItem] = useState("New Chat");

  return (
    <aside className="w-64 h-screen bg-sidebar border-r border-sidebar-border flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-sidebar-border">
        <h1 className="text-2xl font-bold text-sidebar-foreground">Script</h1>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-4 space-y-1">
        <SidebarItem 
          icon={MessageSquarePlus} 
          label="New Chat" 
          active={activeItem === "New Chat"}
          onClick={() => setActiveItem("New Chat")}
        />
        <SidebarItem 
          icon={FolderKanban} 
          label="Projects" 
          active={activeItem === "Projects"}
          onClick={() => setActiveItem("Projects")}
        />
        
        <TasksDropdown />
        
        <SidebarItem 
          icon={Clock} 
          label="Recent Chats" 
          active={activeItem === "Recent Chats"}
          onClick={() => setActiveItem("Recent Chats")}
        />
        
        <HistoryDropdown />
        
        <SidebarItem 
          icon={FileText} 
          label="Templates" 
          active={activeItem === "Templates"}
          onClick={() => setActiveItem("Templates")}
        />
        <SidebarItem 
          icon={FileCode} 
          label="Documents" 
          active={activeItem === "Documents"}
          onClick={() => setActiveItem("Documents")}
        />
        <SidebarItem 
          icon={Users} 
          label="Community" 
          active={activeItem === "Community"}
          onClick={() => setActiveItem("Community")}
        />
      </nav>

      {/* Bottom Section */}
      <div className="p-4 border-t border-sidebar-border space-y-1">
        <SidebarItem 
          icon={Settings} 
          label="Settings" 
          active={activeItem === "Settings"}
          onClick={() => setActiveItem("Settings")}
        />
        <SidebarItem 
          icon={HelpCircle} 
          label="Help" 
          active={activeItem === "Help"}
          onClick={() => setActiveItem("Help")}
        />
        
        {/* User Profile */}
        <div className="mt-4 flex items-center gap-3 px-4 py-3 rounded-lg bg-sidebar-accent/30 hover:bg-sidebar-accent/50 transition-all duration-300 cursor-pointer">
          <div className="w-8 h-8 rounded-full bg-accent-blue flex items-center justify-center">
            <User className="w-4 h-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-sidebar-foreground truncate">User</p>
            <p className="text-xs text-muted-foreground truncate">user@example.com</p>
          </div>
        </div>
      </div>
    </aside>
  );
};
