/**
 * The accumulation view: storm footprint under the book, candidate account on top.
 *
 * Three layers, in a deliberate order. The footprint is a server-rendered PNG rather than
 * 20k grid cells shipped as JSON — the colour ramp is identical either way and this costs
 * one bitmap. Exposure points are cold when no storm is loaded and run the heat ramp by
 * loss ratio once one is. Candidate locations are chartreuse and ringed, so the new risk is
 * never confusable with the book you already hold.
 */

import { useEffect, useMemo, useState } from "react";
import DeckGL from "deck.gl";
import { BitmapLayer, ScatterplotLayer } from "deck.gl";
import Map from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";

import type { LocLoss, Loc, Storm } from "../lib/api";
import { footprintUrl } from "../lib/api";
import { eur, heatColour } from "../lib/format";

// Free vector basemap, no API key and no billing relationship. Mapbox would need both.
// Dark, because the whole point of the overlay is that hot colours mean hazard — a light
// basemap washes the footprint out and fights the rest of the interface.
const BASEMAP = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const INITIAL_VIEW = { longitude: 5.5, latitude: 51.0, zoom: 4.4, pitch: 0, bearing: 0 };

type Props = {
  exposure: Loc[];
  losses: LocLoss[] | null;
  candidate: LocLoss[] | null;
  storm: Storm | null;
};

type Point = Loc & { gust_ms?: number; net?: number };

export function AccumulationMap({ exposure, losses, candidate, storm }: Props) {
  const points: Point[] = losses ?? exposure;

  const maxTiv = useMemo(() => Math.max(1, ...points.map((p) => p.tiv)), [points]);

  // Colour by loss ratio relative to the worst-hit location in *this* run rather than a fixed
  // scale. Windstorm loss ratios are small and vary by an order of magnitude between storms;
  // a fixed ceiling renders every point the same colour and hides the concentration that is
  // the entire point of the map.
  const maxLossRatio = useMemo(() => {
    if (!losses) return 0;
    return Math.max(1e-6, ...losses.map((d) => d.net / Math.max(d.tiv, 1)));
  }, [losses]);

  // Load the footprint explicitly so a failure is visible instead of a silently blank overlay.
  const [footprint, setFootprint] = useState<HTMLImageElement | null>(null);
  useEffect(() => {
    if (!storm) {
      setFootprint(null);
      return;
    }
    let cancelled = false;
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => !cancelled && setFootprint(img);
    img.onerror = () => {
      if (!cancelled) {
        console.error("[climate] footprint image failed to load", storm.slug);
        setFootprint(null);
      }
    };
    img.src = footprintUrl(storm.slug);
    return () => {
      cancelled = true;
    };
  }, [storm]);

  const layers = [
    storm &&
      footprint &&
      new BitmapLayer({
        id: `footprint-${storm.slug}`,
        image: footprint,
        bounds: storm.bounds as [number, number, number, number],
        opacity: 0.75,
      }),
    new ScatterplotLayer<Point>({
      id: "exposure",
      data: points,
      getPosition: (d) => [d.lon, d.lat],
      // Area scales with TIV, so a risk twice the size looks twice the size.
      getRadius: (d) => 900 + 5200 * Math.sqrt(d.tiv / maxTiv),
      radiusUnits: "meters",
      radiusMinPixels: 2,
      radiusMaxPixels: 26,
      getFillColor: (d) =>
        d.net === undefined
          ? [91, 143, 201, 165]
          : [...heatColour(d.net / Math.max(d.tiv, 1) / maxLossRatio), 225],
      stroked: false,
      pickable: true,
      updateTriggers: { getFillColor: [losses, maxLossRatio], getRadius: [maxTiv] },
    }),
    candidate &&
      new ScatterplotLayer<LocLoss>({
        id: "candidate",
        data: candidate,
        getPosition: (d) => [d.lon, d.lat],
        getRadius: 7000,
        radiusUnits: "meters",
        radiusMinPixels: 5,
        radiusMaxPixels: 30,
        getFillColor: [198, 242, 78, 60],
        stroked: true,
        lineWidthMinPixels: 2,
        getLineColor: [198, 242, 78, 255],
        pickable: true,
      }),
  ].filter(Boolean);

  return (
    <DeckGL
      initialViewState={INITIAL_VIEW}
      controller={{ dragRotate: false }}
      layers={layers as never[]}
      getTooltip={({ object }) => {
        const o = object as Point | null;
        if (!o) return null;
        const lines = [o.loc_id, `TIV ${eur(o.tiv)}`];
        if (o.gust_ms !== undefined) lines.push(`Gust ${o.gust_ms.toFixed(0)} m/s`);
        if (o.net !== undefined) lines.push(`Loss ${eur(o.net)}`);
        return {
          text: lines.join("\n"),
          style: {
            background: "#080b11",
            border: "1px solid rgba(148,168,200,0.28)",
            color: "#e8edf6",
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: "11px",
            padding: "6px 8px",
          },
        };
      }}
    >
      <Map mapStyle={BASEMAP} attributionControl={false} />
    </DeckGL>
  );
}
