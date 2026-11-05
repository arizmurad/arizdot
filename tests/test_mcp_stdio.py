"""Real stdio server/client tests; no API calls and no UI startup."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

SDK=bool(importlib.util.find_spec('mcp'))
ROOT=Path(__file__).resolve().parents[1]
A='00000000-0000-4000-8000-000000000002'


@unittest.skipUnless(SDK,'Install requirements-claude.txt to test the MCP wire')
class StdioTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_desktop_handshake_is_supported(self):
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters
        with tempfile.TemporaryDirectory() as tmp:
            environment=os.environ.copy();environment['ARIZDOT_DATA_DIR']=tmp
            params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'mcp_server.py')],env=environment,cwd=tmp)
            async with Client(params,mode='legacy') as client:
                result=await client.list_tools()
                self.assertEqual(len(result.tools),6)
                prompt=await client.get_prompt('arizdot')
                self.assertTrue(prompt.messages)

    async def test_real_stdio_discovery_report_status_and_rejected_input(self):
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters
        with tempfile.TemporaryDirectory() as tmp:
            from claude_support import report_desktop
            report_desktop(A,'Fixture task','Starting',root=tmp)
            environment=os.environ.copy();environment['ARIZDOT_DATA_DIR']=tmp
            params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'mcp_server.py')],env=environment,cwd=tmp)
            async with Client(params) as client:
                tools=await client.list_tools()
                self.assertEqual({t.name for t in tools.tools},{'arizdot_open','arizdot_report','arizdot_status','arizdot_job_register','arizdot_job_update','arizdot_jobs'})
                report_tool=next(t for t in tools.tools if t.name=='arizdot_report')
                self.assertEqual(set(report_tool.input_schema['properties']['phase']['enum']),{'working','waiting','completed','error'})
                prompts=await client.list_prompts()
                self.assertIn('arizdot',[p.name for p in prompts.prompts])
                prompt=await client.get_prompt('arizdot')
                self.assertTrue(prompt.messages)
                result=await client.call_tool('arizdot_report',dict(monitor_id=A,current='Checking inputs',completed=2,total=5,next_step='Run validation'))
                self.assertFalse(result.is_error)
                result=await client.call_tool('arizdot_status',dict(monitor_id=A))
                self.assertFalse(result.is_error)
                text=''.join(c.text for c in result.content if c.type=='text')
                data=json.loads(text)
                self.assertEqual(data['percent'],40)
                self.assertEqual(data['freshness'],'recorded')
                self.assertFalse(data['working'])
                bad=await client.call_tool('arizdot_report',dict(monitor_id=A,current='Invalid',completed=9,total=5))
                self.assertTrue(bad.is_error)
                boolean=await client.call_tool('arizdot_report',dict(monitor_id=A,current='Invalid',completed=True,total=5))
                self.assertTrue(boolean.is_error)
                unknown=await client.call_tool('arizdot_status',dict(monitor_id='../../private'))
                self.assertTrue(unknown.is_error)
                # Failed updates do not mutate the last valid report.
                result=await client.call_tool('arizdot_status',dict(monitor_id=A))
                data=json.loads(''.join(c.text for c in result.content if c.type=='text'))
                self.assertEqual(data['current'],'Checking inputs')
                result=await client.call_tool('arizdot_report',dict(monitor_id=A,current='Review',steps=[dict(step='Check inputs',status='completed'),dict(step='Review',status='in_progress')],next_step='Publish draft'))
                self.assertFalse(result.is_error)
                data=json.loads(''.join(c.text for c in result.content if c.type=='text'))
                self.assertEqual(data['percent'],50)
                result=await client.call_tool('arizdot_report',dict(monitor_id=A,title='Next task',current='New task work',new_turn=True))
                self.assertFalse(result.is_error)
                data=json.loads(''.join(c.text for c in result.content if c.type=='text'))
                self.assertEqual(data['title'],'Next task');self.assertEqual(data['current'],'New task work')
                self.assertIsNone(data['percent']);self.assertFalse(data['next_step'])
                registered=await client.call_tool('arizdot_job_register',dict(monitor_id=A,title='Background export',source={'type':'reported'},run_id='export-one'))
                self.assertFalse(registered.is_error)
                job=json.loads(''.join(c.text for c in registered.content if c.type=='text'))
                updated=await client.call_tool('arizdot_job_update',dict(monitor_id=A,job_id=job['job_id'],status=dict(state='running',current='Exporting',completed=1,total=3)))
                self.assertFalse(updated.is_error)
                await client.call_tool('arizdot_report',dict(monitor_id=A,current='Reply done',phase='completed'))
                listing=await client.call_tool('arizdot_jobs',dict(monitor_id=A))
                rows=json.loads(''.join(c.text for c in listing.content if c.type=='text'))
                self.assertEqual(rows['jobs'][0]['job_id'],job['job_id'])


if __name__=='__main__':unittest.main()
