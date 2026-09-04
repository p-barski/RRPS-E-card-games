import { useEffect, useState } from "react";
import "./App.css";
import { ECardGame } from "./games/ecard/ECardGame";
import { RPSGame } from "./games/rps/RPSGame";
import { Home } from "./pages/Home";
import { MuteButton } from "./shared/MuteButton";
import type { GameType } from "./shared/types";

type Route = { view: "home" } | { view: GameType; code: string };

function parseRoute(): Route {
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (parts.length === 2 && (parts[0] === "rps" || parts[0] === "ecard")) {
    return { view: parts[0], code: parts[1] };
  }
  return { view: "home" };
}

export default function App() {
  const [route, setRoute] = useState<Route>(parseRoute());

  useEffect(() => {
    const onPopState = () => setRoute(parseRoute());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function enterRoom(gameType: GameType, code: string) {
    window.history.pushState(null, "", `/${gameType}/${code}`);
    setRoute({ view: gameType, code });
  }

  function goHome() {
    window.history.pushState(null, "", "/");
    setRoute({ view: "home" });
  }

  return (
    <>
      <MuteButton />
      {route.view === "home" && <Home onEnterRoom={enterRoom} />}
      {route.view === "rps" && <RPSGame code={route.code} onExit={goHome} />}
      {route.view === "ecard" && <ECardGame code={route.code} onExit={goHome} />}
    </>
  );
}
