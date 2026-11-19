import { NavLink } from "react-router-dom";
import { LayoutDashboard, Cloud, Search, Shield } from "lucide-react";
import clsx from "clsx";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard", end: true },
  { to: "/accounts", icon: Cloud, label: "Accounts", end: false },
  { to: "/scans", icon: Search, label: "Scans", end: false },
];

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-60 flex-col bg-[#1a1a2e] text-gray-300">
      <div className="flex items-center gap-2 border-b border-white/10 px-5 py-5">
        <Shield className="h-7 w-7 text-emerald-400" />
        <span className="text-lg font-bold tracking-tight text-white">
          SafeScale
        </span>
      </div>

      <nav className="mt-4 flex flex-1 flex-col gap-1 px-3">
        {navItems.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-emerald-500/15 text-emerald-400"
                  : "hover:bg-white/5 hover:text-white",
              )
            }
          >
            <Icon className="h-5 w-5" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 px-5 py-4 text-xs text-gray-500">
        SafeScale v0.1.0
      </div>
    </aside>
  );
}
