"""Not a permanent script -- delete after use."""
import truststore
truststore.inject_into_ssl()

from app.agents.research.repositories.research_repository import get_latest_snapshot
from app.agents.research.state import VisualsData

for domain in ["apromore.com", "servicenow.com", "appian.com", "palantir.com", "uipath.com", "celonis.com"]:
    row = get_latest_snapshot(domain, "visuals")
    data = VisualsData.model_validate(row)
    print(f"\n=== {domain} ({len(data.logo)} logos) ===")
    for url in data.logo:
        print(" ", url)
