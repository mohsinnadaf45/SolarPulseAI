import { Features } from "@/components/landing/Features";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { SiteFooter } from "@/components/landing/SiteFooter";
import { SiteHeader } from "@/components/landing/SiteHeader";

export default function Home() {
  return (
    <main>
      <SiteHeader />
      <Hero />
      <Features />
      <HowItWorks />
      <SiteFooter />
    </main>
  );
}
