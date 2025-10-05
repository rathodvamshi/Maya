import { Plus, MoreVertical, Pin, Trash2, Edit2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface Project {
  id: string;
  title: string;
  preview: string;
  pinned?: boolean;
}

const projects: Project[] = [
  {
    id: "1",
    title: "E-commerce Platform",
    preview: "Building a modern online store with React and Node.js",
    pinned: true,
  },
  {
    id: "2",
    title: "Portfolio Website",
    preview: "Personal portfolio showcasing design projects",
  },
  {
    id: "3",
    title: "Task Management App",
    preview: "Productivity tool with calendar integration",
  },
  {
    id: "4",
    title: "Social Media Dashboard",
    preview: "Analytics dashboard for multiple platforms",
  },
  {
    id: "5",
    title: "Weather Application",
    preview: "Real-time weather data with beautiful UI",
  },
  {
    id: "6",
    title: "Recipe Finder",
    preview: "Search and save your favorite recipes",
  },
  {
    id: "7",
    title: "Fitness Tracker",
    preview: "Track workouts and monitor progress",
  },
];

interface ProjectsPanelProps {
  isOpen: boolean;
}

export const ProjectsPanel = ({ isOpen }: ProjectsPanelProps) => {
  if (!isOpen) return null;

  return (
    <aside className="w-80 h-screen border-l border-border bg-card flex flex-col animate-slide-in-right">
      {/* Header */}
      <div className="p-6 border-b border-border flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">
          Projects <span className="text-muted-foreground text-sm">(7)</span>
        </h2>
        <Button
          size="sm"
          className="h-8 w-8 p-0 bg-accent-blue hover:bg-accent-blue/90 text-white rounded-lg"
        >
          <Plus className="w-4 h-4" />
        </Button>
      </div>

      {/* Projects List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {projects.map((project, index) => (
          <div
            key={project.id}
            className="p-4 rounded-xl border border-border bg-background hover:shadow-md hover:-translate-y-1 transition-all duration-300 cursor-pointer group animate-fade-in-scale"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2 flex-1 min-w-0">
                {project.pinned && (
                  <Pin className="w-3 h-3 text-accent-blue shrink-0" />
                )}
                <h3 className="font-semibold text-sm text-foreground truncate">
                  {project.title}
                </h3>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="bg-popover">
                  <DropdownMenuItem>
                    <Pin className="w-3 h-3 mr-2" />
                    Pin
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    <Edit2 className="w-3 h-3 mr-2" />
                    Rename
                  </DropdownMenuItem>
                  <DropdownMenuItem className="text-destructive">
                    <Trash2 className="w-3 h-3 mr-2" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            <p className="text-xs text-muted-foreground line-clamp-2">
              {project.preview}
            </p>
          </div>
        ))}
      </div>
    </aside>
  );
};
