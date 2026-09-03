#if WITH_DEV_AUTOMATION_TESTS

#include "HAL/PlatformProcess.h"
#include "Misc/AutomationTest.h"
#include "MotionWorldUdpTransport.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldUdpTransportTest,
	"MotionWorld.Protocol.BoundedNonblockingUdp",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldUdpTransportTest::RunTest(const FString& Parameters)
{
	using namespace MotionWorld;

	FMotionWorldUdpTransportConfig Invalid;
	Invalid.RemotePort = Invalid.LocalPort;
	TestFalse(TEXT("One endpoint cannot send to itself"), Invalid.IsValid());
	Invalid.RemotePort = 52581;
	Invalid.MaxInboundDatagramBytes = MaxUdpPayloadBytes;
	TestFalse(TEXT("Inbound size leaves oversize detection room"), Invalid.IsValid());

	FMotionWorldUdpTransportConfig UnrealConfig;
	UnrealConfig.LocalPort = 52680;
	UnrealConfig.RemotePort = 52681;
	UnrealConfig.MaxInboundDatagramBytes = 4;
	UnrealConfig.MaxOutboundDatagramBytes = 16;
	UnrealConfig.MaxDatagramsPerPoll = 4;

	FMotionWorldUdpTransportConfig PythonConfig;
	PythonConfig.LocalPort = UnrealConfig.RemotePort;
	PythonConfig.RemotePort = UnrealConfig.LocalPort;
	PythonConfig.MaxInboundDatagramBytes = 16;
	PythonConfig.MaxOutboundDatagramBytes = 16;
	PythonConfig.MaxDatagramsPerPoll = 4;

	FMotionWorldUdpTransport UnrealTransport;
	FMotionWorldUdpTransport PythonTransport;
	if (!TestTrue(TEXT("Unreal endpoint opens"), UnrealTransport.Open(UnrealConfig))
		|| !TestTrue(TEXT("Python endpoint opens"), PythonTransport.Open(PythonConfig)))
	{
		return false;
	}

	const uint8 ValidBytes[] = {'o', 'k'};
	const uint8 OversizedBytes[] = {'1', '2', '3', '4', '5'};
	TestTrue(TEXT("Bounded datagram sends"), PythonTransport.Send(ValidBytes));
	TestTrue(TEXT("Receiver-bound oversize still reaches transport"), PythonTransport.Send(OversizedBytes));
	TestFalse(TEXT("Empty datagram is rejected before send"), PythonTransport.Send({}));

	FMotionWorldUdpPollResult PollResult;
	for (int32 Attempt = 0; Attempt < 100 && PollResult.DatagramsRead < 2; ++Attempt)
	{
		const FMotionWorldUdpPollResult Next = UnrealTransport.Poll();
		PollResult.DatagramsRead += Next.DatagramsRead;
		PollResult.RejectedUnknownSender += Next.RejectedUnknownSender;
		PollResult.RejectedOversizedOrEmpty += Next.RejectedOversizedOrEmpty;
		PollResult.Payloads.Append(Next.Payloads);
		if (PollResult.DatagramsRead < 2)
		{
			FPlatformProcess::SleepNoStats(0.001f);
		}
	}

	TestEqual(TEXT("Both datagrams were drained"), PollResult.DatagramsRead, 2);
	TestEqual(TEXT("Only the bounded datagram survives"), PollResult.Payloads.Num(), 1);
	if (PollResult.Payloads.Num() == 1)
	{
		TestEqual(TEXT("Bounded payload length is exact"), PollResult.Payloads[0].Num(), 2);
		TestEqual(TEXT("First payload byte is exact"), PollResult.Payloads[0][0], uint8('o'));
		TestEqual(TEXT("Second payload byte is exact"), PollResult.Payloads[0][1], uint8('k'));
	}
	TestEqual(
		TEXT("Oversized datagram is rejected before parsing"),
		PollResult.RejectedOversizedOrEmpty,
		1);

	UnrealTransport.Close();
	PythonTransport.Close();
	TestFalse(TEXT("Closed endpoint reports closed"), UnrealTransport.IsOpen());
	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
