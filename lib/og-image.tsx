import { SITE_NAME, SITE_TAGLINE } from "@/lib/config";

export const SOCIAL_IMAGE_SIZE = { width: 1200, height: 630 };
export const SOCIAL_IMAGE_ALT = `${SITE_NAME}. ${SITE_TAGLINE} Kanıt temelli iddia incelemesi.`;

export function SocialImage() {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        backgroundColor: "#f6f7f5",
        color: "#151a21",
        padding: "72px 104px",
      }}
    >
      <div style={{ color: "#173f5f", fontFamily: "Georgia, serif", fontSize: 148, fontWeight: 700, lineHeight: 1.1 }}>
        {SITE_NAME}
      </div>
      <div style={{ width: "100%", height: 2, backgroundColor: "#d4d9dd", marginTop: 30, marginBottom: 38 }} />
      <div style={{ fontSize: 42, fontWeight: 700 }}>{SITE_TAGLINE}</div>
      <div style={{ color: "#45586a", fontSize: 29, marginTop: 18 }}>Kanıt temelli iddia incelemesi</div>
    </div>
  );
}
