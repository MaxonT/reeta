import { useEffect, useMemo, useRef, useState } from 'react'
import { ReactFlow, ReactFlowProvider, Handle, Position, useReactFlow } from '@xyflow/react'
import { api } from '../lib/api.js'

const LAYOUT = {
  self_call: { x: 160, y: 0 },
  base_case: { x: 0, y: 120 },
  smaller_problem: { x: 0, y: 250 },
  independent_frames: { x: 320, y: 120 },
  return_propagation: { x: 320, y: 250 },
}
// Fallback if GET /concepts/edges fails; the API reads them from answer_key.json.
const EDGES = [
  ['self_call', 'base_case'], ['base_case', 'smaller_problem'],
  ['self_call', 'independent_frames'], ['independent_frames', 'return_propagation'],
  ['smaller_problem', 'return_propagation'],
]

function ConceptNode({ data }) {
  return (
    <div className={`cnode ${data.status} ${data.highlight ? 'hl' : ''}`}>
      <Handle type="target" position={Position.Top} />
      <div className="cnode-label">{data.label}</div>
      <div className="cnode-status">{data.status === 'missing' ? 'never taught' : data.status}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}
const nodeTypes = { concept: ConceptNode }

// Refit whenever the container resizes (scene transitions start at width 0).
function AutoFit({ box }) {
  const { fitView } = useReactFlow()
  useEffect(() => {
    if (!box.current) return
    const ro = new ResizeObserver(() => fitView({ padding: 0.15 }))
    ro.observe(box.current)
    return () => ro.disconnect()
  }, [fitView])
  return null
}

// 5 nodes: green = correct, red = misconception, dashed gray = missing.
export default function ConceptMap(props) {
  return <ReactFlowProvider><Map {...props} /></ReactFlowProvider>
}

function Map({ concepts = [], highlight = [], height = 380, onSelect }) {
  const box = useRef(null)
  const [edgeList, setEdgeList] = useState(EDGES)
  useEffect(() => {
    let live = true
    api.conceptEdges()
      .then((r) => { if (live && Array.isArray(r?.edges) && r.edges.length) setEdgeList(r.edges) })
      .catch(() => {})
    return () => { live = false }
  }, [])
  const nodes = useMemo(() => concepts.map((c) => ({
    id: c.id, type: 'concept', position: LAYOUT[c.id] || { x: 0, y: 0 },
    data: { label: c.label, status: c.status, highlight: highlight.includes(c.id) },
  })), [concepts, highlight])
  const edges = useMemo(() => edgeList.map(([s, t]) => ({
    id: `${s}-${t}`, source: s, target: t,
    style: { stroke: '#7a6a55', strokeDasharray: '6 4', strokeWidth: 2 },
  })), [edgeList])
  return (
    <div className="concept-map" style={{ height }} ref={box}>
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.15 }}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
        zoomOnScroll={false} panOnDrag={false} zoomOnDoubleClick={false} preventScrolling={false}
        onNodeClick={(_, n) => onSelect?.(n.id)} >
        <AutoFit box={box} />
      </ReactFlow>
    </div>
  )
}
