import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { Footer } from "@/components/marketing/Footer";
import { Hero } from "@/components/marketing/Hero";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { MultiAgentExplainer } from "@/components/marketing/MultiAgentExplainer";
import { Nav } from "@/components/marketing/Nav";
import { ProblemSection } from "@/components/marketing/ProblemSection";

export default function HomePage() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <ProblemSection />
        <HowItWorks />
        <FeatureGrid />
        <MultiAgentExplainer />
      </main>
      <Footer />
    </>
  );
}
