"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FileText,
  Building2,
  GitCompareArrows,
  Settings,
} from "lucide-react";
import { LogoFull } from "@/components/logo";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Reports", href: "/reports", icon: FileText },
  { name: "Comparisons", href: "/comparisons", icon: GitCompareArrows },
  { name: "Brands", href: "/brands", icon: Building2 },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-[220px] flex-col border-r border-border bg-background">
      <div className="px-5 py-4 border-b border-border">
        <LogoFull />
      </div>

      <nav className="flex-1 px-3 py-3 space-y-0.5">
        {navigation.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : item.href === "/comparisons"
                ? pathname.startsWith("/comparisons") || pathname.startsWith("/compare")
                : pathname.startsWith(item.href);

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium transition-colors",
                isActive
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border px-5 py-3">
        <p className="text-2xs text-muted-foreground">CRM Intelligence Engine v0.1.0</p>
      </div>
    </aside>
  );
}
