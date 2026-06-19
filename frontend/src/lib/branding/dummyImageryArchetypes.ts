import type { ImageryArchetypes } from "./types";

/**
 * Placeholder for the (not-yet-built) branding agent's imagery-archetype
 * clustering output. Swap `useImageryArchetypes`'s queryFn for a real
 * `/branding/imagery-archetypes` call once that endpoint exists — every
 * component consuming this shape keeps working unchanged.
 */
export const DUMMY_IMAGERY_ARCHETYPES: ImageryArchetypes = {
  archetypes: [
    {
      name: "Abstract Gradient",
      description:
        "Soft, colorful gradients and blurred shapes used as backgrounds behind product screenshots or headlines — common on SaaS landing pages aiming for a modern, approachable feel.",
      image: "https://picsum.photos/seed/abstract-gradient/480/360",
      companies: ["Celonis", "ServiceNow", "UiPath"],
    },
    {
      name: "Real-world Photography",
      description:
        "Photos of real people, offices, and customer environments — used to ground the brand in tangible, human use cases rather than abstract software concepts.",
      image: "https://picsum.photos/seed/real-photography/480/360",
      companies: ["Microsoft", "SAP"],
    },
    {
      name: "Illustration & Iconography",
      description:
        "Flat, geometric illustrations and custom icon sets used to explain workflows and concepts without relying on photography or product UI.",
      image: "https://picsum.photos/seed/illustration-icons/480/360",
      companies: ["Apromore", "ARIS"],
    },
    {
      name: "Product UI Screens",
      description:
        "Cropped screenshots and mockups of the actual product interface — leaning on the dashboard/data-visualization look itself as the primary visual asset.",
      image: "https://picsum.photos/seed/product-ui-screens/480/360",
      companies: ["Celonis", "UiPath", "ServiceNow"],
    },
  ],
  generatedAt: null,
};
