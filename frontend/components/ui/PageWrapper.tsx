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
    <div className="lg:ml-36 gap-24 flex flex-col min-h-screen">
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
