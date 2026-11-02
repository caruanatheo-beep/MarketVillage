// Remove unused facade blocks instead of squeezing the playable world. All layers
// share this projection: tile collisions, furniture, lights and the terrace.
export function worldY(row:number):number {
  const compact = row<=17?row:row<19?17:row-2;
  // The two landings at raw rows 19/20 share one level; facade gaps must not
  // look like extra empty storeys between every department.
  return compact - (row>=20?1:0) + (row>=9?1:0);
}

// Department coordinates are shared by the collision map, furniture and lights.
export function wingPosition(col:number,row:number):{col:number;row:number} {
  // North walls and their glazing follow exactly the same setback as the room.
  if (row===9 && col>=3 && col<=14) return {col:col-2,row:worldY(row)};
  if (row===9 && col>=32) return {col,row:worldY(row)-1};
  if (row>=10 && row<=16 && col<=15) return {col:col-2,row:worldY(row)};
  if (row>=22 && row<=30 && col>=1 && col<=14) return {col:col-1,row:worldY(row)};
  if (row>=10 && row<=16 && col>=32) return {col,row:worldY(row)-1};
  return {col,row:worldY(row)};
}
