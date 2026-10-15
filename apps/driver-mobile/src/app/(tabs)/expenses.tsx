import ExpenseScreen from "../../expenses/ExpenseScreen";
import { useDriver } from "../../driver/context";

export default function Expenses() {
  const state = useDriver();
  return <ExpenseScreen key={state.user?.id ?? "signed-out"} />;
}
