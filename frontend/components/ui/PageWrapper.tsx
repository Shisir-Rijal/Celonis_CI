import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import Footer from "../Footer";

type PageWrapperProps = {
  children: React.ReactNode;
};

export default function PageWrapper({
  children,
}: PageWrapperProps) {
  return (
    <div className="lg:pt-16 flex flex-col min-h-screen bg-primary-black text-primary-white">
      <div
        className={twMerge(
          clsx("flex flex-col gap-24 px-16 py-22 justify-start items-start flex-1")
        )}
      >
        {children}
      </div>
      <Footer />
    </div>
  );
}
