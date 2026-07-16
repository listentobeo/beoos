"use client";

import * as React from "react";
import { motion, useMotionValue, useSpring } from "framer-motion";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface IconProps {
  id: number;
  icon: React.FC<React.SVGProps<SVGSVGElement>>;
  className: string;
  label?: string;
}

export interface FloatingIconsHeroProps {
  title: string;
  eyebrow?: string;
  subtitle: string;
  ctaText: string;
  ctaHref: string;
  secondaryCtaText?: string;
  secondaryCtaHref?: string;
  icons: IconProps[];
}

const Icon = ({
  mouseX,
  mouseY,
  iconData,
  index,
}: {
  mouseX: React.MutableRefObject<number>;
  mouseY: React.MutableRefObject<number>;
  iconData: IconProps;
  index: number;
}) => {
  const ref = React.useRef<HTMLDivElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 260, damping: 22 });
  const springY = useSpring(y, { stiffness: 260, damping: 22 });
  const floatDuration = 5 + (index % 5) * 0.7;

  React.useEffect(() => {
    const handleMouseMove = () => {
      if (!ref.current) return;
      const rect = ref.current.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const distance = Math.sqrt(
        Math.pow(mouseX.current - centerX, 2) + Math.pow(mouseY.current - centerY, 2),
      );

      if (distance < 150) {
        const angle = Math.atan2(mouseY.current - centerY, mouseX.current - centerX);
        const force = (1 - distance / 150) * 48;
        x.set(-Math.cos(angle) * force);
        y.set(-Math.sin(angle) * force);
      } else {
        x.set(0);
        y.set(0);
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [mouseX, mouseY, x, y]);

  return (
    <motion.div
      ref={ref}
      style={{ x: springX, y: springY }}
      initial={{ opacity: 0, scale: 0.55 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.06, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className={cn("absolute hidden sm:block", iconData.className)}
      aria-label={iconData.label}
    >
      <motion.div
        className="flex size-14 items-center justify-center rounded-3xl border border-white/70 bg-white/85 p-3 shadow-[0_24px_70px_rgba(16,24,39,0.14)] backdrop-blur md:size-16 lg:size-20"
        animate={{
          y: [0, -8, 0, 8, 0],
          x: [0, 6, 0, -6, 0],
          rotate: [0, 4, 0, -4, 0],
        }}
        transition={{
          duration: floatDuration,
          repeat: Infinity,
          repeatType: "mirror",
          ease: "easeInOut",
        }}
      >
        <iconData.icon className="size-8 md:size-10" />
      </motion.div>
    </motion.div>
  );
};

const FloatingIconsHero = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & FloatingIconsHeroProps
>(
  (
    {
      className,
      title,
      eyebrow,
      subtitle,
      ctaText,
      ctaHref,
      secondaryCtaText,
      secondaryCtaHref,
      icons,
      ...props
    },
    ref,
  ) => {
    const mouseX = React.useRef(0);
    const mouseY = React.useRef(0);

    const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
      mouseX.current = event.clientX;
      mouseY.current = event.clientY;
    };

    return (
      <section
        ref={ref}
        onMouseMove={handleMouseMove}
        className={cn(
          "relative isolate flex min-h-[720px] w-full items-center justify-center overflow-hidden bg-[#f5f4f0]",
          className,
        )}
        {...props}
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(237,99,63,0.18),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(16,24,39,0.14),transparent_34%)]" />
        <div className="absolute inset-x-8 top-10 h-64 rounded-full bg-white/45 blur-3xl" />
        <div className="absolute inset-0">
          {icons.map((iconData, index) => (
            <Icon key={iconData.id} mouseX={mouseX} mouseY={mouseY} iconData={iconData} index={index} />
          ))}
        </div>

        <div className="relative z-10 mx-auto max-w-5xl px-5 py-24 text-center">
          {eyebrow && (
            <p className="mx-auto inline-flex rounded-full border border-[#ed633f]/20 bg-white/80 px-4 py-2 text-sm font-black text-[#ed633f] shadow-sm backdrop-blur">
              {eyebrow}
            </p>
          )}
          <h1 className="mx-auto mt-6 max-w-4xl text-5xl font-black tracking-[-0.055em] text-[#101827] md:text-7xl">
            {title}
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-[#59605a]">
            {subtitle}
          </p>
          <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
            <Button asChild className="h-12 rounded-full px-7 text-base font-black shadow-sm">
              <a href={ctaHref}>{ctaText}</a>
            </Button>
            {secondaryCtaText && secondaryCtaHref && (
              <Button asChild variant="outline" className="h-12 rounded-full px-7 text-base font-black">
                <a href={secondaryCtaHref}>{secondaryCtaText}</a>
              </Button>
            )}
          </div>
          <div className="mx-auto mt-8 flex max-w-2xl flex-wrap items-center justify-center gap-2 text-xs font-bold text-[#6f746f]">
            {["WhatsApp", "Gmail", "Zoho", "Forms", "CRM", "Quotes", "Pricing", "Alerts"].map((item) => (
              <span key={item} className="rounded-full border bg-white/70 px-3 py-1.5 backdrop-blur">
                {item}
              </span>
            ))}
          </div>
        </div>
      </section>
    );
  },
);

FloatingIconsHero.displayName = "FloatingIconsHero";

export { FloatingIconsHero };
