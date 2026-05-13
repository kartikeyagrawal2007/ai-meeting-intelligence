"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Upload,
  Zap,
  Database,
  Activity,
  Cpu,
} from "lucide-react";
import { cn } from "@/lib/utils";
import TokenBadge from "./TokenBadge";

const NAV = [
  { href: "/",          icon: Upload,          label: "Upload" },
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
];

export default function Sidebar() {
  const path = usePathname();

  return (
    <aside className="w-60 flex-shrink-0 flex flex-col border-r border-[#1e293b] bg-[#0d1424]">
      {/* Logo */}
      <div className="px-5 py-6 border-b border-[#1e293b]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <Cpu className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white leading-none">MeetingAI</p>
            <p className="text-[10px] text-slate-500 mt-0.5">Intelligence Platform</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = path === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                active
                  ? "bg-indigo-500/15 text-indigo-300 shadow-sm border border-indigo-500/20"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
              )}
            >
              <Icon className={cn("w-4 h-4", active ? "text-indigo-400" : "")} />
              {label}
              {active && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-indigo-400" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Token usage widget */}
      <div className="px-3 pb-4">
        <TokenBadge />
      </div>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-[#1e293b]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 pulse-dot" />
          <p className="text-xs text-slate-500">API Connected</p>
        </div>
      </div>
    </aside>
  );
}
