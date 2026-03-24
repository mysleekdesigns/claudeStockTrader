import Link from "next/link";

const links = [
  { href: "/", label: "Trading" },
  { href: "/brain", label: "Brain" },
  { href: "/health", label: "Health" },
];

export function Nav() {
  return (
    <nav className="flex h-14 items-center justify-between border-b border-border bg-surface px-6">
      <div className="flex items-center gap-6">
        <Link href="/" className="text-sm font-bold tracking-wide text-gold-400">
          XAU/USD TRADER
        </Link>
        <div className="flex items-center gap-4">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
