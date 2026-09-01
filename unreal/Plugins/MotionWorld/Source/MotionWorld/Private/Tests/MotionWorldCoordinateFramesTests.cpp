#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldCoordinateFrames.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldCoordinateFramesTest,
	"MotionWorld.Coordinates.PlanarVelocity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldCoordinateFramesTest::RunTest(const FString& Parameters)
{
	using MotionWorld::CharacterLocalToWorldPlanarVelocity;
	using MotionWorld::WorldToCharacterLocalPlanarVelocity;

	constexpr double Tolerance = 1.e-6;
	const FVector LocalForward(200.0, 0.0, 25.0);

	TestTrue(
		TEXT("Yaw 0 keeps local forward on world +X and removes Z"),
		CharacterLocalToWorldPlanarVelocity(LocalForward, 0.0)
			.Equals(FVector(200.0, 0.0, 0.0), Tolerance));
	TestTrue(
		TEXT("Yaw 90 maps local forward to world +Y"),
		CharacterLocalToWorldPlanarVelocity(LocalForward, 90.0)
			.Equals(FVector(0.0, 200.0, 0.0), Tolerance));
	TestTrue(
		TEXT("Yaw 180 maps local forward to world -X"),
		CharacterLocalToWorldPlanarVelocity(LocalForward, 180.0)
			.Equals(FVector(-200.0, 0.0, 0.0), Tolerance));
	TestTrue(
		TEXT("Yaw -90 maps local forward to world -Y"),
		CharacterLocalToWorldPlanarVelocity(LocalForward, -90.0)
			.Equals(FVector(0.0, -200.0, 0.0), Tolerance));

	const FVector LocalRight(0.0, 200.0, 0.0);
	TestTrue(
		TEXT("Yaw 90 maps local right to world -X"),
		CharacterLocalToWorldPlanarVelocity(LocalRight, 90.0)
			.Equals(FVector(-200.0, 0.0, 0.0), Tolerance));

	const FVector ArbitraryLocal(123.0, -45.0, 0.0);
	const FVector ArbitraryWorld =
		CharacterLocalToWorldPlanarVelocity(ArbitraryLocal, 37.0);
	TestTrue(
		TEXT("Local-to-world-to-local round trip recovers the original planar vector"),
		WorldToCharacterLocalPlanarVelocity(ArbitraryWorld, 37.0)
			.Equals(ArbitraryLocal, Tolerance));

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
