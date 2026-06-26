import Button from "../../../components/ui/Button";
import SectionWrapper from "../../../components/ui/SectionWrapper";

export default function Home() {
  return (
    <main className="flex flex-col gap-[inherit] w-full">

      {/*Page heading*/}
      <div className="flex-col gap-16">
        <h1 className="text-neutral-grey-20">Competitor Dashboard</h1>
        <div className="flex flex-row gap-2 items-center">
          <div className="bg-secondary-green rounded w-3 h-3"/>
          <h3 className="text-primary-black">Test paragraph</h3>
        </div>
      </div>

      <SectionWrapper label="Test heading">
        <Button><h4>Test</h4></Button>
      </SectionWrapper>

      <SectionWrapper label="Test heading">
        <Button><h4>Test</h4></Button>
      </SectionWrapper>

      <div className="flex flex-row gap-8">
        <SectionWrapper label="Test heading" className="w-1/2">
          <Button><h4>Test</h4></Button>
        </SectionWrapper>
        <SectionWrapper label="Test heading" className="w-1/2">
          <Button><h4>Test</h4></Button>
        </SectionWrapper>
      </div>

      <SectionWrapper label="Test heading">
        <Button><h4>Test</h4></Button>
      </SectionWrapper>

    </main>
  );
}
