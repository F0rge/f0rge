import { TrashCan } from "@carbon/icons-react";
import { Button, Table, TableBody, TableCell, TableHead, TableHeader, TableRow, Tag } from "@carbon/react";
import { formatZarAmount, type PriceList } from "@/lib/api";
import styles from "./price-lists.module.css";

interface PriceListItemsProps {
  list: PriceList;
  busy?: boolean;
  onRemove?: (skuId: string) => void;
}

export function PriceListItems({ list, busy = false, onRemove }: PriceListItemsProps) {
  return <div className={styles.items}>
    <Table size="sm" aria-label={`${list.name} prices`}>
      <TableHead><TableRow><TableHeader>Our ref</TableHeader><TableHeader>Unit ex VAT</TableHeader>{onRemove && <TableHeader><span className="cds--visually-hidden">Actions</span></TableHeader>}</TableRow></TableHead>
      <TableBody>{list.items.length ? list.items.map((item) => <TableRow key={item.sku_id}>
        <TableCell>{item.our_ref}</TableCell>
        <TableCell>{formatZarAmount(item.unit_ex_vat)}{item.below_average_cost && <Tag type="red" size="sm">Below average cost</Tag>}</TableCell>
        {onRemove && <TableCell><Button kind="ghost" size="sm" renderIcon={TrashCan} hasIconOnly iconDescription={`Remove ${item.our_ref}`} disabled={busy} onClick={() => onRemove(item.sku_id)} /></TableCell>}
      </TableRow>) : <TableRow><TableCell colSpan={onRemove ? 3 : 2}>No prices added yet.</TableCell></TableRow>}</TableBody>
    </Table>
  </div>;
}
