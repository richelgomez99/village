import type { ComponentType, ReactNode } from "react";
import { BigButton, ContactCard, Header, Screen, Stack, StatusGrid, Text } from "../components/primitives";
import { Alert, CareRota, DoseTracker, HelperAnswer, LifeAreas, PillOrganizer, RefillCard, Timeline, TonightCard } from "../components/care";
import { IncidentCard, Proposal, ScamCheck, VerificationPrompt } from "../components/money";
import { GenericBoard, Checklist, VillageChat } from "../components/generic";

export interface CatalogProps {
  id: string;
  props: Record<string, any>;
  children?: ReactNode;
}

export const CATALOG: Record<string, ComponentType<CatalogProps>> = {
  Screen, Stack, Header, Text, BigButton, ContactCard, StatusGrid,
  Alert, DoseTracker, HelperAnswer, Timeline, CareRota, LifeAreas, PillOrganizer,
  VerificationPrompt, IncidentCard, ScamCheck, Proposal,
  SourceCard: GenericBoard, SymptomLog: GenericBoard, CallLog: GenericBoard, NeedBoard: GenericBoard,
  ResourceBoard: GenericBoard, VerifiedInfoFeed: GenericBoard, CheckIn: GenericBoard,
  Checklist, VillageChat,
  // 1.2.2 (D22)
  RefillCard, TonightCard
};
