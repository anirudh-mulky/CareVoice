import { ClipboardList, FilePlus2, LayoutDashboard } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { VoiceServicesProvider } from "@/shared/VoiceServicesProvider";

const LINKS = [
  { to: "/doctor", label: "Patients", icon: LayoutDashboard, end: true },
  { to: "/doctor/discharge/new", label: "New discharge", icon: FilePlus2, end: false },
  { to: "/doctor/templates", label: "Templates", icon: ClipboardList, end: false },
];

/** Staff area shell. Round 2 has no login: it runs as the demo doctor. */
export function DoctorLayout() {
  return (
    <div className="flex flex-1 flex-col gap-6 pb-10">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-3">
        <nav aria-label="Doctor" className="flex flex-wrap gap-1">
          {LINKS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive ? "bg-secondary text-secondary-foreground" : "text-muted-foreground hover:bg-accent",
                )
              }
            >
              <Icon className="size-4" aria-hidden /> {label}
            </NavLink>
          ))}
        </nav>
        <Badge variant="outline" title="Round 2 demo: no login">
          Demo · Dr. Priya
        </Badge>
      </div>
      {/* Real mode: dictation is transcribed on the server. */}
      <VoiceServicesProvider>
        <Outlet />
      </VoiceServicesProvider>
    </div>
  );
}
