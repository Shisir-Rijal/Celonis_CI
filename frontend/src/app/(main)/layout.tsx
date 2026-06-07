import NavBar from "../../../components/ui/Navbar";
import PageWrapper from "../../../components/ui/PageWrapper";

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <NavBar />
      <PageWrapper>{children}</PageWrapper>
    </>
  );
}
