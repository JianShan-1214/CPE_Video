import React from "react";
import { useThemeColors } from "./calculate-metadata/theme";

export const TITLE_BAR_HEIGHT = 40;
export const TAB_BAR_HEIGHT = 30;
export const IDE_INSET = 10;

// 上方 85% 的高度（1080 * 0.85）
export const CODE_SECTION_HEIGHT = Math.floor(1080 * 0.85); // 918
export const SUBTITLE_HEIGHT = 1080 - CODE_SECTION_HEIGHT; // 162

export const CODE_AREA_HEIGHT =
  CODE_SECTION_HEIGHT - IDE_INSET * 2 - TITLE_BAR_HEIGHT - TAB_BAR_HEIGHT; // 800

const TrafficLight: React.FC<{ color: string }> = ({ color }) => (
  <div
    style={{
      width: 13,
      height: 13,
      borderRadius: "50%",
      backgroundColor: color,
      flexShrink: 0,
    }}
  />
);

export const IDEFrame: React.FC<{
  filename: string;
  children: React.ReactNode;
}> = ({ filename, children }) => {
  // The window chrome follows the selected code theme, otherwise picking a
  // theme in the editor would only recolour the tokens and leave a
  // github-dark shell around them.
  const colors = useThemeColors();
  const editorBg = colors.editor.background;
  const chromeBg = colors.editorGroupHeader.tabsBackground;
  const border = `1px solid ${colors.editorGroup.border}`;

  const outerStyle: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    backgroundColor: chromeBg,
  };

  const windowStyle: React.CSSProperties = {
    position: "absolute",
    inset: IDE_INSET,
    borderRadius: 10,
    overflow: "hidden",
    boxShadow: "0 16px 60px rgba(0,0,0,0.8)",
    display: "flex",
    flexDirection: "column",
    backgroundColor: editorBg,
    border,
  };

  const titleBarStyle: React.CSSProperties = {
    height: TITLE_BAR_HEIGHT,
    backgroundColor: chromeBg,
    display: "flex",
    alignItems: "center",
    padding: "0 16px",
    gap: 7,
    flexShrink: 0,
    position: "relative",
    borderBottom: border,
  };

  const titleTextStyle: React.CSSProperties = {
    position: "absolute",
    left: 0,
    right: 0,
    textAlign: "center",
    color: colors.editorLineNumber.foreground,
    fontSize: 15,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    pointerEvents: "none",
  };

  const tabBarStyle: React.CSSProperties = {
    height: TAB_BAR_HEIGHT,
    backgroundColor: chromeBg,
    display: "flex",
    alignItems: "flex-end",
    flexShrink: 0,
    borderBottom: border,
  };

  const tabStyle: React.CSSProperties = {
    height: "88%",
    padding: "0 18px",
    display: "flex",
    alignItems: "center",
    backgroundColor: colors.tab.activeBackground,
    color: colors.tab.activeForeground,
    fontSize: 16,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    borderRight: border,
    borderTop: "2px solid #f78166",
    borderTopLeftRadius: 3,
    borderTopRightRadius: 3,
  };

  const codeAreaStyle: React.CSSProperties = {
    flex: 1,
    overflow: "hidden",
    position: "relative",
  };

  return (
    <div style={outerStyle}>
      <div style={windowStyle}>
        <div style={titleBarStyle}>
          <TrafficLight color="#ff5f57" />
          <TrafficLight color="#ffbd2e" />
          <TrafficLight color="#28c840" />
          <span style={titleTextStyle}>{filename}</span>
        </div>
        <div style={tabBarStyle}>
          <div style={tabStyle}>{filename}</div>
        </div>
        <div style={codeAreaStyle}>{children}</div>
      </div>
    </div>
  );
};
