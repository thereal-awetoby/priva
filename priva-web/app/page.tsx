import Masthead from "@/components/Masthead";
import Hero from "@/components/Hero";
import ThesisSection from "@/components/ThesisSection";
import HowItWorksSection from "@/components/HowItWorksSection";
import PrivacySection from "@/components/PrivacySection";
import DashboardPreview from "@/components/DashboardPreview";
import SiteFooter from "@/components/SiteFooter";

export default function Home() {
  return (
    <>
      <Masthead />
      <Hero />
      <ThesisSection />
      <HowItWorksSection />
      <PrivacySection />
      <DashboardPreview />
      <SiteFooter />
    </>
  );
}